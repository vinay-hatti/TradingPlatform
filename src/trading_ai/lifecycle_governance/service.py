from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from trading_ai.autonomous_position_management.models import M73ExitReservationModel, M73PositionManagerModel
from trading_ai.portfolio_intelligence.models import ManagedPositionModel, PositionEventModel
from trading_ai.position_management.database_models import PositionExitInstructionModel


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class LifecycleGovernanceService:
    """M75 terminal-position lifecycle finalization and certification.

    The service deliberately does not alter entry pricing, exit trigger semantics, or
    broker routing.  It owns the boundary between an operational position and an
    archived/terminal position.  Safe local artifacts are finalized automatically;
    potentially live broker mutations remain fail-closed and are reported instead of
    being silently discarded.
    """

    VERSION = "M75.0-LIFECYCLE-GOVERNANCE-AUTONOMOUS-OPERATIONS-CERTIFICATION-1.0"
    ACTIVE_POSITION_STATES = {"OPEN", "PARTIAL", "HEDGED", "ROLLED", "ACTIVE", "MANAGED"}
    TERMINAL_POSITION_STATES = {"CLOSED", "EXPIRED", "ASSIGNED", "STOPPED", "TERMINAL", "ARCHIVED", "SUPERSEDED"}
    SAFE_FINALIZABLE_INSTRUCTION_STATES = {
        "ARMED", "SUBMISSION_FAILED", "PENDING_APPROVAL", "TRIGGERED_ADVISORY",
        "READY_FOR_AUTOMATIC_SUBMISSION", "APPROVED", "PENDING_RETRY", "WAITING",
    }
    BROKER_WORKING_INSTRUCTION_STATES = {"SUBMITTED", "ACKNOWLEDGED", "PARTIAL", "REPRICE_PENDING", "CANCEL_REQUESTED"}
    TERMINAL_INSTRUCTION_STATES = {"CANCELLED", "CANCELED", "FILLED", "REJECTED", "FAILED", "SUPERSEDED", "COMPLETED"}
    ACTIVE_RESERVATION_STATES = {"RESERVED", "SUBMITTED", "PARTIAL"}

    def __init__(self, session: Session):
        self.s = session

    def _event(self, position: ManagedPositionModel, event_type: str, actor: str, reason: str, payload: dict) -> None:
        self.s.add(PositionEventModel(
            event_id=f"PE-{uuid4().hex.upper()}",
            position_id=position.position_id,
            position_version=position.version,
            event_type=event_type,
            actor=actor,
            reason=reason,
            event_timestamp=utc_now(),
            payload_json=payload,
        ))

    def _terminal_reason(self, position: ManagedPositionModel) -> str:
        state = str(position.state or "").upper()
        return {
            "CLOSED": "POSITION_CLOSED",
            "EXPIRED": "POSITION_EXPIRED",
            "ASSIGNED": "POSITION_ASSIGNED",
            "STOPPED": "POSITION_STOPPED",
            "SUPERSEDED": "POSITION_SUPERSEDED",
            "ARCHIVED": "POSITION_ARCHIVED",
            "TERMINAL": "POSITION_TERMINAL",
        }.get(state, f"POSITION_{state or 'TERMINAL'}")

    def _instructions(self, position_id: str) -> list[PositionExitInstructionModel]:
        return list(self.s.scalars(
            select(PositionExitInstructionModel)
            .where(PositionExitInstructionModel.position_id == position_id)
            .order_by(PositionExitInstructionModel.id)
        ))

    def _manager(self, position_id: str):
        return self.s.scalar(select(M73PositionManagerModel).where(M73PositionManagerModel.position_id == position_id))

    def _reservations(self, position_id: str):
        return list(self.s.scalars(select(M73ExitReservationModel).where(M73ExitReservationModel.position_id == position_id)))

    def finalize_terminal_position(self, position: ManagedPositionModel, actor: str = "M75_LIFECYCLE_FINALIZER") -> dict:
        state = str(position.state or "").upper()
        if state not in self.TERMINAL_POSITION_STATES:
            return {"position_id": position.position_id, "status": "NOT_TERMINAL", "state": state}

        reason = self._terminal_reason(position)
        now = utc_now()
        instructions = self._instructions(position.position_id)
        working = [x for x in instructions if str(x.status or "").upper() in self.BROKER_WORKING_INSTRUCTION_STATES]
        if working:
            # Never hide a potentially live broker mutation just because the local
            # position is terminal.  Reconciliation/cancellation must settle it first.
            metadata = dict(position.metadata_json or {})
            metadata["lifecycle_governance"] = {
                "version": self.VERSION,
                "status": "BLOCKED_BROKER_MUTATION_PENDING",
                "terminal_reason": reason,
                "blocked_instruction_ids": [x.instruction_id for x in working],
                "checked_at": now,
            }
            position.metadata_json = metadata
            position.updated_at = now
            return {
                "position_id": position.position_id,
                "symbol": position.symbol,
                "status": "BLOCKED_BROKER_MUTATION_PENDING",
                "terminal_reason": reason,
                "blocked_instruction_ids": [x.instruction_id for x in working],
            }

        finalized_instructions = 0
        for instruction in instructions:
            status = str(instruction.status or "").upper()
            if status in self.TERMINAL_INSTRUCTION_STATES:
                continue
            if status not in self.SAFE_FINALIZABLE_INSTRUCTION_STATES:
                continue
            payload = dict(instruction.payload or {})
            history = list(payload.get("lifecycle_history") or [])
            history.append({
                "prior_status": instruction.status,
                "terminal_reason": reason,
                "finalized_at": now,
                "finalized_by": actor,
                "version": self.VERSION,
                "submission_error": payload.get("submission_error"),
            })
            payload["lifecycle_history"] = history[-50:]
            payload["lifecycle_status"] = "TERMINAL"
            payload["terminal_reason"] = reason
            payload["terminal_at"] = now
            payload["terminal_actor"] = actor
            payload["terminal_prior_status"] = instruction.status
            instruction.payload = payload
            instruction.status = "CANCELLED"
            instruction.quantity = 0
            finalized_instructions += 1

        manager = self._manager(position.position_id)
        manager_finalized = False
        if manager is not None:
            md = dict(manager.metadata_json or {})
            md.update({
                "lifecycle_status": "TERMINAL",
                "terminal_reason": reason,
                "finalized_at": now,
                "finalized_by": actor,
                "version": self.VERSION,
            })
            manager.metadata_json = md
            manager.state = "FINALIZED"
            manager.protection_state = "FINALIZED"
            manager.last_decision = "POSITION_TERMINAL"
            manager_finalized = True

        reservations_finalized = 0
        for reservation in self._reservations(position.position_id):
            if str(reservation.status or "").upper() not in self.ACTIVE_RESERVATION_STATES:
                continue
            reservation.status = "CANCELLED"
            if hasattr(reservation, "metadata_json"):
                md = dict(getattr(reservation, "metadata_json", None) or {})
                md.update({"terminal_reason": reason, "finalized_at": now, "finalized_by": actor, "version": self.VERSION})
                reservation.metadata_json = md
            reservations_finalized += 1

        metadata = dict(position.metadata_json or {})
        ownership = dict(metadata.get("position_ownership") or {})
        ownership.update({
            "lifecycle": "TERMINAL",
            "bootstrap_state": "FINALIZED",
            "active_exit_count": 0,
            "manager_state": "FINALIZED" if manager_finalized else ownership.get("manager_state"),
            "last_bootstrap_check_at": now,
        })
        metadata["position_ownership"] = ownership
        metadata["m73_management"] = "FINALIZED"
        metadata["m75_lifecycle_status"] = "FINALIZED"
        metadata["lifecycle_governance"] = {
            "version": self.VERSION,
            "status": "FINALIZED",
            "terminal_reason": reason,
            "finalized_at": now,
            "finalized_by": actor,
            "instructions_finalized": finalized_instructions,
            "reservations_finalized": reservations_finalized,
            "manager_finalized": manager_finalized,
        }
        position.metadata_json = metadata
        position.updated_at = now
        position.version += 1
        self._event(
            position,
            "M75_TERMINAL_POSITION_FINALIZED",
            actor,
            "Finalized autonomous lifecycle for terminal managed position",
            dict(metadata["lifecycle_governance"]),
        )
        return {
            "position_id": position.position_id,
            "symbol": position.symbol,
            "status": "FINALIZED",
            "terminal_reason": reason,
            "instructions_finalized": finalized_instructions,
            "reservations_finalized": reservations_finalized,
            "manager_finalized": manager_finalized,
        }

    def reconcile_terminal_positions(self, portfolio_id: str | None = None, actor: str = "M75_LIFECYCLE_FINALIZER", commit: bool = True) -> dict:
        query = select(ManagedPositionModel).where(ManagedPositionModel.state.in_(self.TERMINAL_POSITION_STATES))
        if portfolio_id:
            query = query.where(ManagedPositionModel.portfolio_id == portfolio_id)
        rows = list(self.s.scalars(query))
        finalized = 0
        blocked = 0
        details = []
        for position in rows:
            result = self.finalize_terminal_position(position, actor=actor)
            details.append(result)
            if result.get("status") == "FINALIZED":
                finalized += 1
            elif result.get("status") == "BLOCKED_BROKER_MUTATION_PENDING":
                blocked += 1
        if commit:
            self.s.commit()
        else:
            self.s.flush()
        return {
            "version": self.VERSION,
            "portfolio_id": portfolio_id,
            "terminal_positions_scanned": len(rows),
            "positions_finalized": finalized,
            "positions_blocked": blocked,
            "details": details,
        }

    def audit(self, portfolio_id: str | None = None) -> dict:
        query = select(ManagedPositionModel)
        if portfolio_id:
            query = query.where(ManagedPositionModel.portfolio_id == portfolio_id)
        positions = list(self.s.scalars(query))
        violations = []
        certified_terminal = 0
        active_positions = 0
        for position in positions:
            state = str(position.state or "").upper()
            instructions = self._instructions(position.position_id)
            manager = self._manager(position.position_id)
            reservations = self._reservations(position.position_id)
            if state in self.ACTIVE_POSITION_STATES:
                active_positions += 1
                continue
            if state not in self.TERMINAL_POSITION_STATES:
                continue
            bad_instructions = [x for x in instructions if str(x.status or "").upper() not in self.TERMINAL_INSTRUCTION_STATES]
            active_reservations = [x for x in reservations if str(x.status or "").upper() in self.ACTIVE_RESERVATION_STATES]
            manager_active = bool(manager is not None and str(manager.state or "").upper() == "ACTIVE")
            if bad_instructions or active_reservations or manager_active:
                violations.append({
                    "position_id": position.position_id,
                    "symbol": position.symbol,
                    "state": state,
                    "active_instruction_ids": [x.instruction_id for x in bad_instructions],
                    "active_reservation_count": len(active_reservations),
                    "manager_state": getattr(manager, "state", None),
                })
            else:
                certified_terminal += 1
        return {
            "version": self.VERSION,
            "portfolio_id": portfolio_id,
            "status": "CERTIFIED" if not violations else "VIOLATIONS_FOUND",
            "positions_scanned": len(positions),
            "active_positions": active_positions,
            "certified_terminal_positions": certified_terminal,
            "violation_count": len(violations),
            "violations": violations,
        }

    def certify(self, portfolio_id: str | None = None, actor: str = "M75_CERTIFICATION", repair_safe: bool = False) -> dict:
        repair = None
        if repair_safe:
            repair = self.reconcile_terminal_positions(portfolio_id=portfolio_id, actor=actor, commit=False)
        audit = self.audit(portfolio_id=portfolio_id)
        if repair_safe:
            self.s.commit()
        return {"version": self.VERSION, "repair": repair, "audit": audit}
