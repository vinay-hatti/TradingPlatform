from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
import uuid

from .paper_trading_policy import PaperTradingAutomationPolicy
from .paper_trading_profile import (
    PaperTradingCycleProfile,
    PaperTradingRuntimeState,
    PaperTradingSessionProfile,
)
from .paper_trading_runtime_repository import (
    JsonPaperTradingRuntimeRepository,
)
from .paper_trading_session_engine import PaperTradingSessionEngine
from .paper_trading_state_machine import PaperTradingSessionStateMachine


class PaperTradingSessionService:
    def __init__(
        self,
        *,
        policy: PaperTradingAutomationPolicy | None = None,
        repository: JsonPaperTradingRuntimeRepository | None = None,
    ) -> None:
        self.policy = policy or PaperTradingAutomationPolicy()
        self.repository = (
            repository or JsonPaperTradingRuntimeRepository()
        )
        self.engine = PaperTradingSessionEngine(self.policy)
        self.state_machine = PaperTradingSessionStateMachine(self.policy)

    def create(
        self,
        profile: PaperTradingSessionProfile,
    ):
        if (
            self.policy.require_unique_session_id
            and self.repository.get(profile.session_id) is not None
        ):
            raise ValueError(
                f"Paper-trading session already exists: {profile.session_id}"
            )
        decision, state = self.engine.create(profile)
        if state is not None:
            self.repository.save(state)
        return decision, state

    def transition(self, session_id: str, action: str):
        state = self.repository.require(session_id)
        decision, updated = self.state_machine.transition(state, action)
        if decision.allowed:
            self.repository.save(updated)
        return decision, updated

    def begin_cycle(
        self,
        session_id: str,
    ) -> tuple[PaperTradingRuntimeState, PaperTradingCycleProfile]:
        state = self.repository.require(session_id)
        if state.session.state != "RUNNING":
            raise ValueError("Cycles may only begin while session is RUNNING")
        if state.cycle_count >= self.policy.maximum_cycles_per_session:
            raise ValueError("Maximum session cycle count reached")

        now = datetime.now(timezone.utc).isoformat()
        cycle = PaperTradingCycleProfile(
            cycle_id=f"cycle-{uuid.uuid4().hex}",
            session_id=session_id,
            sequence_number=state.cycle_count + 1,
            started_at=now,
            scanned_symbols=state.session.symbols,
        )
        updated_session = replace(
            state.session,
            last_cycle_at=now,
        )
        updated = replace(
            state,
            session=updated_session,
            cycle_count=state.cycle_count + 1,
            last_cycle=cycle,
            version=state.version + 1,
            updated_at=now,
        )
        self.repository.save(updated)
        return updated, cycle

    def complete_cycle(
        self,
        session_id: str,
        *,
        candidate_count: int,
        approved_count: int,
        submitted_count: int,
        rejected_count: int,
        errors: tuple[str, ...] = (),
    ) -> PaperTradingRuntimeState:
        state = self.repository.require(session_id)
        if state.last_cycle is None:
            raise ValueError("No active paper-trading cycle")
        if submitted_count > self.policy.maximum_orders_per_cycle:
            raise ValueError("Cycle submitted-order limit exceeded")
        if (
            state.orders_submitted + submitted_count
            > self.policy.maximum_orders_per_session
        ):
            raise ValueError("Session submitted-order limit exceeded")

        now = datetime.now(timezone.utc).isoformat()
        cycle = replace(
            state.last_cycle,
            completed_at=now,
            state="FAILED" if errors else "COMPLETED",
            candidate_count=candidate_count,
            approved_count=approved_count,
            submitted_count=submitted_count,
            rejected_count=rejected_count,
            errors=errors,
        )
        updated = replace(
            state,
            orders_created=state.orders_created + candidate_count,
            orders_submitted=state.orders_submitted + submitted_count,
            orders_rejected=state.orders_rejected + rejected_count,
            last_cycle=cycle,
            recovery_required=bool(errors),
            recovery_reason=(
                "CYCLE_ERRORS" if errors else state.recovery_reason
            ),
            version=state.version + 1,
            updated_at=now,
        )
        self.repository.save(updated)
        return updated
