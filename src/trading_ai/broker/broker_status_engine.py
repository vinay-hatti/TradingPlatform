from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from typing import Iterable

from .broker_execution_profile import BrokerOrderStateProfile
from .broker_reconciliation_policy import BrokerReconciliationPolicy
from .broker_status_profile import (
    BrokerFillEvent,
    BrokerOrderExecutionSummary,
    BrokerOrderStatusEvent,
)


def _parse(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _ordered_quantity(state: BrokerOrderStateProfile) -> float:
    if not state.order.legs:
        return 0.0
    return max(
        leg.quantity * max(leg.ratio, 1)
        for leg in state.order.legs
    )


class BrokerOrderStatusEngine:
    """Apply status and fill events to normalized broker order states."""

    def __init__(
        self,
        policy: BrokerReconciliationPolicy | None = None,
    ) -> None:
        self.policy = policy or BrokerReconciliationPolicy()
        self.policy.validate()

    def validate_status_event(
        self,
        state: BrokerOrderStateProfile,
        event: BrokerOrderStatusEvent,
    ) -> tuple[str, ...]:
        reasons: list[str] = []
        if event.broker_order_id != state.broker_order_id:
            reasons.append("BROKER_ORDER_ID_MISMATCH")
        if event.client_order_id != state.client_order_id:
            reasons.append("CLIENT_ORDER_ID_MISMATCH")
        if event.account_id != state.account_id:
            reasons.append("ACCOUNT_ID_MISMATCH")
        if event.status.upper() not in self.policy.allowed_order_statuses:
            reasons.append("ORDER_STATUS_INVALID")
        if self.policy.reject_negative_fills and event.filled_quantity < 0:
            reasons.append("NEGATIVE_FILLED_QUANTITY")
        if (
            self.policy.require_monotonic_fill_quantity
            and event.filled_quantity + self.policy.maximum_quantity_difference
            < state.filled_quantity
        ):
            reasons.append("FILLED_QUANTITY_REGRESSION")
        ordered = _ordered_quantity(state)
        if (
            self.policy.reject_overfills
            and event.filled_quantity
            > ordered + self.policy.maximum_quantity_difference
        ):
            reasons.append("ORDER_OVERFILL")
        return tuple(reasons)

    def validate_fill_event(
        self,
        state: BrokerOrderStateProfile,
        event: BrokerFillEvent,
    ) -> tuple[str, ...]:
        reasons: list[str] = []
        if event.broker_order_id != state.broker_order_id:
            reasons.append("BROKER_ORDER_ID_MISMATCH")
        if event.client_order_id != state.client_order_id:
            reasons.append("CLIENT_ORDER_ID_MISMATCH")
        if event.account_id != state.account_id:
            reasons.append("ACCOUNT_ID_MISMATCH")
        if self.policy.reject_negative_fills and event.quantity <= 0:
            reasons.append("FILL_QUANTITY_INVALID")
        if event.price <= 0:
            reasons.append("FILL_PRICE_INVALID")
        leg_ids = {leg.leg_id for leg in state.order.legs}
        if event.leg_id not in leg_ids:
            reasons.append("FILL_LEG_NOT_FOUND")
        return tuple(reasons)

    def summarize(
        self,
        state: BrokerOrderStateProfile,
        fills: Iterable[BrokerFillEvent],
        status_events: Iterable[BrokerOrderStatusEvent] = (),
    ) -> BrokerOrderExecutionSummary:
        valid_fills = [
            fill
            for fill in fills
            if not self.validate_fill_event(state, fill)
        ]
        ordered = _ordered_quantity(state)
        filled = sum(fill.quantity for fill in valid_fills)
        gross_notional = sum(
            fill.quantity * fill.price
            for fill in valid_fills
        )
        commission = sum(fill.commission for fill in valid_fills)
        fees = sum(fill.fees for fill in valid_fills)
        average_fill_price = (
            gross_notional / filled if filled > 0 else None
        )

        latest_status = state.status
        last_event_at = state.updated_at
        valid_status_events = []
        for event in status_events:
            if not self.validate_status_event(state, event):
                valid_status_events.append(event)

        if valid_status_events:
            latest_event = max(
                valid_status_events,
                key=lambda item: _parse(item.event_timestamp),
            )
            latest_status = latest_event.status.upper()
            last_event_at = latest_event.event_timestamp

        if filled >= ordered - self.policy.maximum_quantity_difference:
            latest_status = "FILLED"
        elif filled > 0 and latest_status not in {
            "CANCELED",
            "REJECTED",
            "EXPIRED",
        }:
            latest_status = "PARTIALLY_FILLED"

        net_cash_flow = gross_notional - commission - fees
        return BrokerOrderExecutionSummary(
            broker_order_id=state.broker_order_id,
            client_order_id=state.client_order_id,
            status=latest_status,
            ordered_quantity=ordered,
            filled_quantity=filled,
            remaining_quantity=max(0.0, ordered - filled),
            average_fill_price=average_fill_price,
            gross_notional=gross_notional,
            commission=commission,
            fees=fees,
            net_cash_flow=net_cash_flow,
            fill_count=len(valid_fills),
            last_event_at=last_event_at,
        )
