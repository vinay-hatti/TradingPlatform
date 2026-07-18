from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock
from uuid import uuid4

from trading_ai.ui.models.paper_commands import (
    AuditEvent,
    CommandDecision,
    PaperOrderCancelRequest,
    PaperOrderRecord,
    PaperOrderReplaceRequest,
    PaperOrderStatus,
    PaperOrderSubmitRequest,
    PaperTradingState,
    PaperTradingSummary,
)
from trading_ai.ui.policies.paper_command_policy import PaperCommandPolicy


class JsonPaperCommandRepository:
    def __init__(
        self,
        state_path: Path | str = "reports/ui/paper_trading_state.json",
        audit_path: Path | str = "reports/audit/paper_command_events.jsonl",
    ):
        self.state_path = Path(state_path)
        self.audit_path = Path(audit_path)
        self._lock = RLock()

    def load_orders(self) -> list[PaperOrderRecord]:
        with self._lock:
            if not self.state_path.exists():
                return []
            payload = json.loads(self.state_path.read_text(encoding="utf-8"))
            return [
                PaperOrderRecord.model_validate(item)
                for item in payload.get("orders", [])
            ]

    def save_orders(self, orders: list[PaperOrderRecord]) -> None:
        with self._lock:
            self.state_path.parent.mkdir(parents=True, exist_ok=True)
            payload = {
                "updated_at": datetime.now(timezone.utc).isoformat(),
                "orders": [
                    order.model_dump(mode="json")
                    for order in orders
                ],
            }
            temp_path = self.state_path.with_suffix(".tmp")
            temp_path.write_text(
                json.dumps(payload, indent=2, sort_keys=True),
                encoding="utf-8",
            )
            temp_path.replace(self.state_path)

    def append_audit(self, event: AuditEvent) -> None:
        with self._lock:
            self.audit_path.parent.mkdir(parents=True, exist_ok=True)
            with self.audit_path.open("a", encoding="utf-8") as handle:
                handle.write(
                    json.dumps(event.model_dump(mode="json"), sort_keys=True)
                    + "\n"
                )


class PaperCommandService:
    def __init__(
        self,
        repository: JsonPaperCommandRepository | None = None,
        policy: PaperCommandPolicy | None = None,
    ):
        self.repository = repository or JsonPaperCommandRepository()
        self.policy = policy or PaperCommandPolicy()

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)

    @staticmethod
    def _find_idempotent(
        orders: list[PaperOrderRecord],
        idempotency_key: str,
    ) -> PaperOrderRecord | None:
        return next(
            (
                order
                for order in orders
                if order.idempotency_key == idempotency_key
            ),
            None,
        )

    def _audit(
        self,
        *,
        action: str,
        outcome: str,
        actor_user_id: str,
        actor_session_id: str,
        environment: str,
        reason: str,
        detail: str,
        idempotency_key: str,
        resource_id: str | None = None,
    ) -> None:
        self.repository.append_audit(
            AuditEvent(
                event_id=f"evt-{uuid4().hex}",
                occurred_at=self._now(),
                event_type="PAPER_TRADING_COMMAND",
                action=action,
                outcome=outcome,
                actor_user_id=actor_user_id,
                actor_session_id=actor_session_id,
                environment=environment,
                resource_id=resource_id,
                reason=reason,
                detail=detail,
                idempotency_key=idempotency_key,
            )
        )

    def state(self) -> PaperTradingState:
        orders = self.repository.load_orders()
        open_statuses = {
            PaperOrderStatus.PENDING,
            PaperOrderStatus.ACCEPTED,
            PaperOrderStatus.PARTIALLY_FILLED,
        }

        return PaperTradingState(
            generated_at=self._now(),
            summary=PaperTradingSummary(
                total_orders=len(orders),
                open_orders=sum(order.status in open_statuses for order in orders),
                filled_orders=sum(
                    order.status == PaperOrderStatus.FILLED
                    for order in orders
                ),
                cancelled_orders=sum(
                    order.status == PaperOrderStatus.CANCELLED
                    for order in orders
                ),
                rejected_orders=sum(
                    order.status == PaperOrderStatus.REJECTED
                    for order in orders
                ),
                gross_notional=sum(
                    order.quantity
                    * (
                        order.limit_price
                        or order.estimated_price
                        or 0.0
                    )
                    for order in orders
                    if order.status != PaperOrderStatus.REJECTED
                ),
            ),
            orders=sorted(
                orders,
                key=lambda order: order.created_at,
                reverse=True,
            ),
            permissions_required=[
                PaperCommandPolicy.VIEW_PERMISSION,
                PaperCommandPolicy.SUBMIT_PERMISSION,
                PaperCommandPolicy.CANCEL_PERMISSION,
                PaperCommandPolicy.REPLACE_PERMISSION,
            ],
            safety_notices=[
                "Live trading is disabled.",
                "All commands are restricted to PAPER or SIMULATION.",
                "Server-side permission, confirmation, idempotency, quantity, "
                "and notional checks are enforced.",
            ],
        )

    def submit(self, request: PaperOrderSubmitRequest) -> CommandDecision:
        orders = self.repository.load_orders()
        replay = self._find_idempotent(orders, request.idempotency_key)
        if replay:
            return CommandDecision(
                allowed=replay.status != PaperOrderStatus.REJECTED,
                status=replay.status.value,
                action="SUBMIT",
                order=replay,
                message="Idempotent replay returned the original decision.",
                policy_reasons=replay.rejection_reasons,
                idempotent_replay=True,
            )

        estimated_price = request.limit_price or request.estimated_price
        reasons = self.policy.authorize(
            action="SUBMIT",
            environment=request.environment,
            actor=request.actor,
            confirmation_token=request.confirmation_token,
            quantity=request.quantity,
            estimated_price=estimated_price,
        )

        now = self._now()
        order = PaperOrderRecord(
            order_id=f"paper-{uuid4().hex[:16]}",
            environment=request.environment,
            symbol=request.symbol,
            instrument_type=request.instrument_type,
            side=request.side,
            order_type=request.order_type,
            quantity=request.quantity,
            limit_price=request.limit_price,
            estimated_price=request.estimated_price,
            option_expiry=request.option_expiry,
            option_strike=request.option_strike,
            option_type=request.option_type,
            status=(
                PaperOrderStatus.REJECTED
                if reasons
                else PaperOrderStatus.ACCEPTED
            ),
            reason=request.reason,
            actor_user_id=request.actor.user_id,
            actor_session_id=request.actor.session_id,
            idempotency_key=request.idempotency_key,
            created_at=now,
            updated_at=now,
            rejection_reasons=reasons,
        )
        orders.append(order)
        self.repository.save_orders(orders)

        self._audit(
            action="SUBMIT",
            outcome=order.status.value,
            actor_user_id=request.actor.user_id,
            actor_session_id=request.actor.session_id,
            environment=request.environment,
            reason=request.reason,
            detail=(
                "Paper order accepted."
                if not reasons
                else "Paper order rejected: " + "; ".join(reasons)
            ),
            idempotency_key=request.idempotency_key,
            resource_id=order.order_id,
        )

        return CommandDecision(
            allowed=not reasons,
            status=order.status.value,
            action="SUBMIT",
            order=order,
            message=(
                "Paper order accepted."
                if not reasons
                else "Paper order rejected by governance policy."
            ),
            policy_reasons=reasons,
        )

    def cancel(
        self,
        order_id: str,
        request: PaperOrderCancelRequest,
    ) -> CommandDecision:
        orders = self.repository.load_orders()
        replay = self._find_idempotent(orders, request.idempotency_key)
        if replay:
            return CommandDecision(
                allowed=True,
                status=replay.status.value,
                action="CANCEL",
                order=replay,
                message="Idempotent replay returned the original decision.",
                idempotent_replay=True,
            )

        target = next(
            (order for order in orders if order.order_id == order_id),
            None,
        )
        if target is None:
            return CommandDecision(
                allowed=False,
                status="NOT_FOUND",
                action="CANCEL",
                message=f"Order {order_id} was not found.",
                policy_reasons=["Unknown paper order."],
            )

        reasons = self.policy.authorize(
            action="CANCEL",
            environment=request.environment,
            actor=request.actor,
            confirmation_token=request.confirmation_token,
        )
        if target.status not in {
            PaperOrderStatus.PENDING,
            PaperOrderStatus.ACCEPTED,
            PaperOrderStatus.PARTIALLY_FILLED,
        }:
            reasons.append(
                f"Order in status {target.status.value} cannot be cancelled."
            )

        if not reasons:
            target.status = PaperOrderStatus.CANCELLED
            target.updated_at = self._now()
            target.reason = request.reason
            target.idempotency_key = request.idempotency_key
            self.repository.save_orders(orders)

        self._audit(
            action="CANCEL",
            outcome="REJECTED" if reasons else "CANCELLED",
            actor_user_id=request.actor.user_id,
            actor_session_id=request.actor.session_id,
            environment=request.environment,
            reason=request.reason,
            detail="; ".join(reasons) if reasons else "Paper order cancelled.",
            idempotency_key=request.idempotency_key,
            resource_id=order_id,
        )

        return CommandDecision(
            allowed=not reasons,
            status="REJECTED" if reasons else "CANCELLED",
            action="CANCEL",
            order=target,
            message=(
                "Paper order cancelled."
                if not reasons
                else "Cancellation rejected by governance policy."
            ),
            policy_reasons=reasons,
        )

    def replace(
        self,
        order_id: str,
        request: PaperOrderReplaceRequest,
    ) -> CommandDecision:
        orders = self.repository.load_orders()
        replay = self._find_idempotent(orders, request.idempotency_key)
        if replay:
            return CommandDecision(
                allowed=True,
                status=replay.status.value,
                action="REPLACE",
                order=replay,
                message="Idempotent replay returned the replacement.",
                idempotent_replay=True,
            )

        target = next(
            (order for order in orders if order.order_id == order_id),
            None,
        )
        if target is None:
            return CommandDecision(
                allowed=False,
                status="NOT_FOUND",
                action="REPLACE",
                message=f"Order {order_id} was not found.",
                policy_reasons=["Unknown paper order."],
            )

        new_quantity = request.quantity or target.quantity
        new_price = (
            request.limit_price
            if request.limit_price is not None
            else target.limit_price or target.estimated_price
        )
        reasons = self.policy.authorize(
            action="REPLACE",
            environment=request.environment,
            actor=request.actor,
            confirmation_token=request.confirmation_token,
            quantity=new_quantity,
            estimated_price=new_price,
        )
        if target.status not in {
            PaperOrderStatus.PENDING,
            PaperOrderStatus.ACCEPTED,
            PaperOrderStatus.PARTIALLY_FILLED,
        }:
            reasons.append(
                f"Order in status {target.status.value} cannot be replaced."
            )

        if reasons:
            self._audit(
                action="REPLACE",
                outcome="REJECTED",
                actor_user_id=request.actor.user_id,
                actor_session_id=request.actor.session_id,
                environment=request.environment,
                reason=request.reason,
                detail="; ".join(reasons),
                idempotency_key=request.idempotency_key,
                resource_id=order_id,
            )
            return CommandDecision(
                allowed=False,
                status="REJECTED",
                action="REPLACE",
                order=target,
                message="Replacement rejected by governance policy.",
                policy_reasons=reasons,
            )

        now = self._now()
        replacement = target.model_copy(
            update={
                "order_id": f"paper-{uuid4().hex[:16]}",
                "quantity": new_quantity,
                "limit_price": request.limit_price
                if request.limit_price is not None
                else target.limit_price,
                "status": PaperOrderStatus.ACCEPTED,
                "reason": request.reason,
                "actor_user_id": request.actor.user_id,
                "actor_session_id": request.actor.session_id,
                "idempotency_key": request.idempotency_key,
                "created_at": now,
                "updated_at": now,
                "replaced_by_order_id": None,
            }
        )
        target.status = PaperOrderStatus.REPLACED
        target.replaced_by_order_id = replacement.order_id
        target.updated_at = now
        orders.append(replacement)
        self.repository.save_orders(orders)

        self._audit(
            action="REPLACE",
            outcome="ACCEPTED",
            actor_user_id=request.actor.user_id,
            actor_session_id=request.actor.session_id,
            environment=request.environment,
            reason=request.reason,
            detail=f"Order replaced by {replacement.order_id}.",
            idempotency_key=request.idempotency_key,
            resource_id=order_id,
        )

        return CommandDecision(
            allowed=True,
            status="ACCEPTED",
            action="REPLACE",
            order=replacement,
            message="Paper order replacement accepted.",
        )
