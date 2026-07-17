from __future__ import annotations
from dataclasses import replace
from datetime import datetime, timezone
from typing import Any
from .order_policy import OrderLifecyclePolicy
from .order_profile import CanonicalOrderAggregate, CanonicalOrderEvent, OrderTransitionCheck, OrderTransitionResult

class OrderLifecycleStateMachine:
    TRANSITIONS = {
        "NEW": {"VALIDATE":"VALIDATED","REJECT":"REJECTED","EXPIRE":"EXPIRED"},
        "VALIDATED": {"ROUTE":"ROUTED","REJECT":"REJECTED","EXPIRE":"EXPIRED"},
        "ROUTED": {"SUBMIT":"SUBMITTED","REJECT":"REJECTED","CANCEL_REQUEST":"CANCEL_PENDING"},
        "SUBMITTED": {"ACKNOWLEDGE":"ACKNOWLEDGED","WORK":"WORKING","PARTIAL_FILL":"PARTIALLY_FILLED","FILL":"FILLED","CANCEL_REQUEST":"CANCEL_PENDING","REPLACE_REQUEST":"REPLACE_PENDING","REJECT":"REJECTED","EXPIRE":"EXPIRED"},
        "ACKNOWLEDGED": {"WORK":"WORKING","PARTIAL_FILL":"PARTIALLY_FILLED","FILL":"FILLED","CANCEL_REQUEST":"CANCEL_PENDING","REPLACE_REQUEST":"REPLACE_PENDING","REJECT":"REJECTED","EXPIRE":"EXPIRED"},
        "WORKING": {"PARTIAL_FILL":"PARTIALLY_FILLED","FILL":"FILLED","CANCEL_REQUEST":"CANCEL_PENDING","REPLACE_REQUEST":"REPLACE_PENDING","REJECT":"REJECTED","EXPIRE":"EXPIRED"},
        "PARTIALLY_FILLED": {"PARTIAL_FILL":"PARTIALLY_FILLED","FILL":"FILLED","CANCEL_REQUEST":"CANCEL_PENDING","REPLACE_REQUEST":"REPLACE_PENDING","EXPIRE":"EXPIRED"},
        "CANCEL_PENDING": {"CANCEL":"CANCELED","PARTIAL_FILL":"PARTIALLY_FILLED","FILL":"FILLED","REJECT":"WORKING"},
        "REPLACE_PENDING": {"REPLACE":"REPLACED","PARTIAL_FILL":"PARTIALLY_FILLED","FILL":"FILLED","REJECT":"WORKING","CANCEL_REQUEST":"CANCEL_PENDING"},
        "REPLACED": {}, "FILLED": {}, "CANCELED": {}, "REJECTED": {}, "EXPIRED": {},
    }
    EVENT_TYPES = {
        "VALIDATE":"ORDER_VALIDATED","ROUTE":"ORDER_ROUTED","SUBMIT":"ORDER_SUBMITTED",
        "ACKNOWLEDGE":"ORDER_ACKNOWLEDGED","WORK":"ORDER_WORKING",
        "PARTIAL_FILL":"ORDER_PARTIALLY_FILLED","FILL":"ORDER_FILLED",
        "CANCEL_REQUEST":"ORDER_CANCEL_REQUESTED","CANCEL":"ORDER_CANCELED",
        "REPLACE_REQUEST":"ORDER_REPLACE_REQUESTED","REPLACE":"ORDER_REPLACED",
        "REJECT":"ORDER_REJECTED","EXPIRE":"ORDER_EXPIRED",
    }

    def __init__(self, policy: OrderLifecyclePolicy | None = None) -> None:
        self.policy = policy or OrderLifecyclePolicy()
        self.policy.validate()

    @staticmethod
    def _grade(score: float) -> tuple[str, str]:
        if score >= 95: return "A", "LOW"
        if score >= 85: return "B", "MODERATE"
        if score >= 70: return "C", "SEVERE"
        return "F", "CRITICAL"

    def transition(self, aggregate: CanonicalOrderAggregate, action: str, *, event_id: str,
                   broker_order_id: str | None = None, filled_quantity: float | None = None,
                   average_fill_price: float | None = None, reason: str | None = None,
                   correlation_id: str | None = None, causation_id: str | None = None,
                   metadata: dict[str, Any] | None = None) -> OrderTransitionResult:
        action = action.strip().upper()
        checks = []
        def add(name, passed, message, required=True, check_metadata=None):
            checks.append(OrderTransitionCheck(name, bool(passed), required, 100.0 if passed else 0.0,
                                               "LOW" if passed else "CRITICAL", message, check_metadata or {}))
        target = self.TRANSITIONS.get(aggregate.state, {}).get(action)
        add("transition_defined", target is not None, "Requested lifecycle transition is defined.",
            check_metadata={"state":aggregate.state,"action":action,"target":target})
        add("terminal_transition", not (aggregate.terminal and self.policy.reject_transitions_from_terminal_states),
            "Terminal aggregate cannot transition further.")
        next_filled = aggregate.filled_quantity if filled_quantity is None else float(filled_quantity)
        if action in {"PARTIAL_FILL","FILL"}:
            add("filled_quantity_non_negative", next_filled >= 0, "Filled quantity cannot be negative.")
            add("filled_quantity_monotonic", not self.policy.reject_fill_quantity_regression or next_filled >= aggregate.filled_quantity,
                "Filled quantity cannot decrease.")
            add("order_overfill", not self.policy.reject_overfills or next_filled <= aggregate.total_quantity,
                "Filled quantity cannot exceed total quantity.")
            if action == "PARTIAL_FILL":
                add("partial_fill_quantity", 0 < next_filled < aggregate.total_quantity,
                    "Partial fill must be above zero and below total quantity.")
            if action == "FILL":
                add("full_fill_quantity", next_filled >= aggregate.total_quantity,
                    "Fill transition requires total quantity to be filled.")
        if action == "CANCEL_REQUEST" and aggregate.state == "PARTIALLY_FILLED":
            add("partial_fill_cancel", self.policy.allow_partial_fill_cancel,
                "Partial-fill cancellation must be permitted.")
        required = [c for c in checks if c.required]
        failed = [c for c in required if not c.passed]
        score = sum(c.score for c in required) / len(required) if required else 100.0
        allowed = not failed if self.policy.fail_closed else target is not None
        grade, severity = self._grade(score)
        if not allowed or target is None:
            return OrderTransitionResult(True, False, action, aggregate, None, round(score,2), grade, severity,
                                         "REJECT", tuple(checks), rejection_reasons=tuple(c.name.upper() for c in failed))
        now = datetime.now(timezone.utc).isoformat()
        remaining = max(0.0, aggregate.total_quantity - next_filled)
        terminal_at = now if target in self.policy.terminal_states else aggregate.terminal_at
        updated = replace(
            aggregate, state=target, version=aggregate.version+1, filled_quantity=next_filled,
            remaining_quantity=remaining,
            average_fill_price=average_fill_price if average_fill_price is not None else aggregate.average_fill_price,
            broker_order_id=broker_order_id or aggregate.broker_order_id,
            replace_count=aggregate.replace_count + 1 if action == "REPLACE" else aggregate.replace_count,
            updated_at=now, terminal_at=terminal_at, last_event_id=event_id,
            metadata={**aggregate.metadata, **(metadata or {})},
        )
        event = CanonicalOrderEvent(
            event_id=event_id, event_type=self.EVENT_TYPES[action], aggregate_id=aggregate.aggregate_id,
            aggregate_version=updated.version, client_order_id=aggregate.client_order_id,
            account_id=aggregate.account_id, event_timestamp=now, previous_state=aggregate.state,
            new_state=target, broker_order_id=updated.broker_order_id,
            filled_quantity=updated.filled_quantity, remaining_quantity=updated.remaining_quantity,
            average_fill_price=updated.average_fill_price, reason=reason,
            correlation_id=correlation_id, causation_id=causation_id, metadata=metadata or {},
        )
        return OrderTransitionResult(True, True, action, updated, event, round(score,2), grade, severity,
                                     "APPLY", tuple(checks))
