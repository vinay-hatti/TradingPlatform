from __future__ import annotations
import uuid
from datetime import datetime, timezone
from typing import Any
from .order_policy import OrderLifecyclePolicy
from .order_profile import CanonicalOrderAggregate, CanonicalOrderCommand, CanonicalOrderEvent, OrderTransitionCheck, OrderTransitionResult

class CanonicalOrderAggregateEngine:
    def __init__(self, policy: OrderLifecyclePolicy | None = None) -> None:
        self.policy = policy or OrderLifecyclePolicy()
        self.policy.validate()

    @staticmethod
    def _grade(score: float) -> tuple[str, str]:
        if score >= 95: return "A", "LOW"
        if score >= 85: return "B", "MODERATE"
        if score >= 70: return "C", "SEVERE"
        return "F", "CRITICAL"

    def create(self, command: CanonicalOrderCommand) -> OrderTransitionResult:
        checks = []
        def add(name, passed, message, required=True, metadata=None):
            checks.append(OrderTransitionCheck(name, bool(passed), required, 100.0 if passed else 0.0,
                                               "LOW" if passed else "CRITICAL", message, metadata or {}))
        add("command_type", command.command_type.upper()=="CREATE", "Aggregate creation requires CREATE command.")
        add("aggregate_id", bool(command.aggregate_id), "Aggregate id is required.")
        add("client_order_id", bool(command.client_order_id) or not self.policy.require_client_order_id,
            "Client order id is required.")
        add("account_id", bool(command.account_id) or not self.policy.require_account_id, "Account id is required.")
        add("idempotency_key", bool(command.idempotency_key) or not self.policy.require_idempotency_key,
            "Idempotency key is required.")
        add("order_type", command.order_type.upper() in self.policy.allowed_order_types, "Order type is supported.")
        add("time_in_force", command.time_in_force.upper() in self.policy.allowed_time_in_force,
            "Time in force is supported.")
        add("leg_count", 0 < len(command.legs) <= self.policy.maximum_legs,
            "Order leg count is within policy.", metadata={"leg_count":len(command.legs)})
        if self.policy.require_limit_price_for_limit_orders and command.order_type.upper() in {"LIMIT","STOP_LIMIT"}:
            add("limit_price", command.limit_price is not None and command.limit_price > 0,
                "Limit price is required and must be positive.")
        if self.policy.require_stop_price_for_stop_orders and command.order_type.upper() in {"STOP","STOP_LIMIT"}:
            add("stop_price", command.stop_price is not None and command.stop_price > 0,
                "Stop price is required and must be positive.")
        if len(command.legs) > 1 and self.policy.reject_market_multi_leg_orders:
            add("multi_leg_market_order", command.order_type.upper() != "MARKET",
                "Multi-leg market orders are not allowed.")
        for leg in command.legs:
            add(f"leg_symbol:{leg.leg_id}", bool(leg.symbol), "Order leg symbol is required.")
            add(f"leg_side:{leg.leg_id}", leg.side.upper() in self.policy.allowed_sides, "Order leg side is supported.")
            add(f"leg_quantity:{leg.leg_id}", self.policy.minimum_quantity <= leg.quantity <= self.policy.maximum_quantity,
                "Order leg quantity is within policy.")
            add(f"leg_position_effect:{leg.leg_id}", leg.position_effect.upper() in self.policy.allowed_position_effects,
                "Order leg position effect is supported.")
            add(f"leg_ratio:{leg.leg_id}", leg.ratio > 0, "Order leg ratio must be positive.")
        required = [c for c in checks if c.required]
        failed = [c for c in required if not c.passed]
        score = sum(c.score for c in required) / len(required) if required else 100.0
        grade, severity = self._grade(score)
        if failed:
            return OrderTransitionResult(True, False, "CREATE", None, None, round(score,2), grade, severity,
                                         "REJECT", tuple(checks), rejection_reasons=tuple(c.name.upper() for c in failed))
        total_quantity = max(leg.quantity * max(leg.ratio,1) for leg in command.legs)
        now = datetime.now(timezone.utc).isoformat()
        event_id = f"evt-{uuid.uuid4().hex}"
        aggregate = CanonicalOrderAggregate(
            aggregate_id=command.aggregate_id, client_order_id=command.client_order_id,
            account_id=command.account_id, idempotency_key=command.idempotency_key,
            order_type=command.order_type.upper(), time_in_force=command.time_in_force.upper(),
            legs=command.legs, state="NEW", version=1, total_quantity=total_quantity,
            filled_quantity=0.0, remaining_quantity=total_quantity, limit_price=command.limit_price,
            stop_price=command.stop_price, outside_regular_hours=command.outside_regular_hours,
            strategy_name=command.strategy_name, root_aggregate_id=command.aggregate_id,
            created_at=now, updated_at=now, last_event_id=event_id, metadata=dict(command.metadata),
        )
        event = CanonicalOrderEvent(
            event_id=event_id, event_type="ORDER_CREATED", aggregate_id=aggregate.aggregate_id,
            aggregate_version=1, client_order_id=aggregate.client_order_id, account_id=aggregate.account_id,
            event_timestamp=now, previous_state="NONE", new_state="NEW", filled_quantity=0.0,
            remaining_quantity=aggregate.remaining_quantity, correlation_id=command.correlation_id,
            causation_id=command.causation_id, metadata=dict(command.metadata),
        )
        return OrderTransitionResult(True, True, "CREATE", aggregate, event, round(score,2),
                                     grade, severity, "APPLY", tuple(checks))
