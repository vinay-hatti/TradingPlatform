from __future__ import annotations

import uuid
from dataclasses import replace
from datetime import datetime, timezone

from .broker_execution_adapter import BrokerOrderExecutionAdapter
from .broker_execution_profile import (
    BrokerCancelRequest,
    BrokerOrderStateProfile,
    BrokerReplaceRequest,
)
from .broker_order_profile import BrokerOrderRequest


def _total_quantity(order: BrokerOrderRequest) -> float:
    if not order.legs:
        return 0.0
    return max(
        leg.quantity * max(leg.ratio, 1)
        for leg in order.legs
    )


class FakeBrokerExecutionAdapter(BrokerOrderExecutionAdapter):
    """Deterministic paper execution adapter."""

    def __init__(self, broker_name: str = "fake") -> None:
        self._broker_name = broker_name
        self._orders: dict[str, BrokerOrderStateProfile] = {}

    @property
    def broker_name(self) -> str:
        return self._broker_name

    def submit_order(
        self,
        order: BrokerOrderRequest,
    ) -> BrokerOrderStateProfile:
        broker_order_id = f"fake-order-{uuid.uuid4().hex[:12]}"
        now = datetime.now(timezone.utc).isoformat()
        total_quantity = _total_quantity(order)
        state = BrokerOrderStateProfile(
            broker=self.broker_name,
            broker_order_id=broker_order_id,
            client_order_id=order.client_order_id,
            account_id=order.account_id,
            status="ACCEPTED",
            order=order,
            filled_quantity=0.0,
            remaining_quantity=total_quantity,
            replace_count=0,
            root_broker_order_id=broker_order_id,
            submitted_at=now,
            updated_at=now,
            metadata={"adapter": "fake"},
        )
        self._orders[broker_order_id] = state
        return state

    def cancel_order(
        self,
        request: BrokerCancelRequest,
    ) -> BrokerOrderStateProfile:
        current = self._orders.get(request.broker_order_id)
        if current is None:
            raise KeyError(f"Unknown broker order: {request.broker_order_id}")

        now = datetime.now(timezone.utc).isoformat()
        updated = replace(
            current,
            status="CANCELED",
            updated_at=now,
            canceled_at=now,
            metadata={
                **current.metadata,
                "cancel_reason": request.reason,
                "cancel_request_id": request.client_request_id,
            },
        )
        self._orders[current.broker_order_id] = updated
        return updated

    def replace_order(
        self,
        request: BrokerReplaceRequest,
    ) -> BrokerOrderStateProfile:
        current = self._orders.get(request.broker_order_id)
        if current is None:
            raise KeyError(f"Unknown broker order: {request.broker_order_id}")

        broker_order_id = f"fake-order-{uuid.uuid4().hex[:12]}"
        now = datetime.now(timezone.utc).isoformat()
        total_quantity = _total_quantity(request.replacement_order)

        replacement = BrokerOrderStateProfile(
            broker=self.broker_name,
            broker_order_id=broker_order_id,
            client_order_id=request.replacement_order.client_order_id,
            account_id=request.replacement_order.account_id,
            status="ACCEPTED",
            order=request.replacement_order,
            filled_quantity=0.0,
            remaining_quantity=total_quantity,
            replace_count=current.replace_count + 1,
            parent_broker_order_id=current.broker_order_id,
            root_broker_order_id=(
                current.root_broker_order_id
                or current.broker_order_id
            ),
            submitted_at=now,
            updated_at=now,
            metadata={
                "adapter": "fake",
                "replace_reason": request.reason,
                "replace_request_id": request.client_request_id,
            },
        )

        old = replace(
            current,
            status="REPLACED",
            updated_at=now,
            metadata={
                **current.metadata,
                "replaced_by": broker_order_id,
            },
        )
        self._orders[current.broker_order_id] = old
        self._orders[broker_order_id] = replacement
        return replacement

    def get_order(
        self,
        broker_order_id: str,
    ) -> BrokerOrderStateProfile | None:
        return self._orders.get(broker_order_id)

    def list_orders(
        self,
        account_id: str | None = None,
    ) -> tuple[BrokerOrderStateProfile, ...]:
        orders = self._orders.values()
        if account_id is not None:
            orders = [
                order
                for order in orders
                if order.account_id == account_id
            ]
        return tuple(
            sorted(
                orders,
                key=lambda item: item.submitted_at,
            )
        )

    def set_status(
        self,
        broker_order_id: str,
        status: str,
        *,
        filled_quantity: float | None = None,
        average_fill_price: float | None = None,
    ) -> BrokerOrderStateProfile:
        current = self._orders[broker_order_id]
        total_quantity = _total_quantity(current.order)
        filled = (
            current.filled_quantity
            if filled_quantity is None
            else float(filled_quantity)
        )
        now = datetime.now(timezone.utc).isoformat()
        updated = replace(
            current,
            status=status.upper(),
            filled_quantity=filled,
            remaining_quantity=max(0.0, total_quantity - filled),
            average_fill_price=average_fill_price,
            updated_at=now,
            filled_at=now if status.upper() == "FILLED" else current.filled_at,
        )
        self._orders[broker_order_id] = updated
        return updated
