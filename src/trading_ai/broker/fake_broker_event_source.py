from __future__ import annotations

import uuid
from datetime import datetime, timezone

from .broker_execution_profile import BrokerOrderStateProfile
from .broker_status_profile import (
    BrokerFillEvent,
    BrokerOrderStatusEvent,
)


class FakeBrokerEventSource:
    """Deterministic status and fill event factory for regression tests."""

    def __init__(self, broker: str = "fake") -> None:
        self.broker = broker
        self._sequence = 0

    def _next_sequence(self) -> int:
        self._sequence += 1
        return self._sequence

    def status(
        self,
        state: BrokerOrderStateProfile,
        status: str,
        *,
        filled_quantity: float = 0.0,
        remaining_quantity: float | None = None,
        average_fill_price: float | None = None,
        reason: str | None = None,
    ) -> BrokerOrderStatusEvent:
        ordered = max(
            (
                leg.quantity * max(leg.ratio, 1)
                for leg in state.order.legs
            ),
            default=0.0,
        )
        return BrokerOrderStatusEvent(
            broker=self.broker,
            broker_order_id=state.broker_order_id,
            client_order_id=state.client_order_id,
            account_id=state.account_id,
            status=status.upper(),
            event_timestamp=datetime.now(timezone.utc).isoformat(),
            sequence_number=self._next_sequence(),
            filled_quantity=filled_quantity,
            remaining_quantity=(
                max(0.0, ordered - filled_quantity)
                if remaining_quantity is None
                else remaining_quantity
            ),
            average_fill_price=average_fill_price,
            reason=reason,
        )

    def fill(
        self,
        state: BrokerOrderStateProfile,
        *,
        leg_id: str,
        symbol: str,
        side: str,
        quantity: float,
        price: float,
        commission: float = 0.0,
        fees: float = 0.0,
    ) -> BrokerFillEvent:
        return BrokerFillEvent(
            broker=self.broker,
            broker_order_id=state.broker_order_id,
            client_order_id=state.client_order_id,
            account_id=state.account_id,
            execution_id=f"exec-{uuid.uuid4().hex[:12]}",
            leg_id=leg_id,
            symbol=symbol,
            side=side,
            quantity=quantity,
            price=price,
            event_timestamp=datetime.now(timezone.utc).isoformat(),
            sequence_number=self._next_sequence(),
            commission=commission,
            fees=fees,
            liquidity="TAKER",
            exchange="PAPER",
        )
