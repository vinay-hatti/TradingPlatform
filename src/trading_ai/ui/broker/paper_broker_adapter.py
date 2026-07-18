from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock
from uuid import uuid4

from trading_ai.ui.models.paper_commands import PaperOrderRecord, PaperOrderStatus
from trading_ai.ui.models.paper_execution import (
    BrokerPaperOrder,
    FillStatus,
    PaperFill,
    PaperPosition,
)


class LocalPaperBrokerAdapter:
    def __init__(
        self,
        state_path: Path | str = "reports/ui/paper_broker_state.json",
    ):
        self.state_path = Path(state_path)
        self._lock = RLock()

    @staticmethod
    def _now():
        return datetime.now(timezone.utc)

    def _load(self) -> dict:
        with self._lock:
            if not self.state_path.exists():
                return {"orders": [], "positions": []}
            return json.loads(self.state_path.read_text(encoding="utf-8"))

    def _save(self, payload: dict) -> None:
        with self._lock:
            self.state_path.parent.mkdir(parents=True, exist_ok=True)
            temp = self.state_path.with_suffix(".tmp")
            temp.write_text(
                json.dumps(payload, indent=2, sort_keys=True),
                encoding="utf-8",
            )
            temp.replace(self.state_path)

    def list_orders(self) -> list[BrokerPaperOrder]:
        payload = self._load()
        return [
            BrokerPaperOrder.model_validate(item)
            for item in payload.get("orders", [])
        ]

    def list_positions(self) -> list[PaperPosition]:
        payload = self._load()
        return [
            PaperPosition.model_validate(item)
            for item in payload.get("positions", [])
        ]

    def submit_from_command(
        self,
        command: PaperOrderRecord,
        market_price: float,
    ) -> BrokerPaperOrder:
        payload = self._load()
        orders = [
            BrokerPaperOrder.model_validate(item)
            for item in payload.get("orders", [])
        ]
        existing = next(
            (
                order
                for order in orders
                if order.client_order_id == command.order_id
            ),
            None,
        )
        if existing:
            return existing

        now = self._now()
        order = BrokerPaperOrder(
            broker_order_id=f"pb-{uuid4().hex[:16]}",
            client_order_id=command.order_id,
            symbol=command.symbol,
            side=command.side.value,
            order_type=command.order_type.value,
            quantity=command.quantity,
            filled_quantity=0,
            remaining_quantity=command.quantity,
            limit_price=command.limit_price,
            status=FillStatus.PENDING,
            submitted_at=now,
            updated_at=now,
        )
        orders.append(order)
        payload["orders"] = [item.model_dump(mode="json") for item in orders]
        self._save(payload)
        return order

    def simulate_fill(
        self,
        broker_order_id: str,
        *,
        market_price: float,
        max_fill_quantity: int | None = None,
        fee_per_contract: float = 0.0,
    ) -> BrokerPaperOrder:
        payload = self._load()
        orders = [
            BrokerPaperOrder.model_validate(item)
            for item in payload.get("orders", [])
        ]
        positions = [
            PaperPosition.model_validate(item)
            for item in payload.get("positions", [])
        ]
        order = next(
            (item for item in orders if item.broker_order_id == broker_order_id),
            None,
        )
        if order is None:
            raise KeyError(f"Unknown broker paper order: {broker_order_id}")
        if order.status in {
            FillStatus.FILLED,
            FillStatus.CANCELLED,
            FillStatus.REJECTED,
        }:
            return order

        eligible = (
            order.order_type == "MARKET"
            or order.limit_price is None
            or (
                order.side == "BUY" and market_price <= order.limit_price
            )
            or (
                order.side == "SELL" and market_price >= order.limit_price
            )
        )
        if not eligible:
            order.updated_at = self._now()
            payload["orders"] = [
                item.model_dump(mode="json") for item in orders
            ]
            self._save(payload)
            return order

        fill_quantity = min(
            order.remaining_quantity,
            max_fill_quantity or order.remaining_quantity,
        )
        fill = PaperFill(
            fill_id=f"fill-{uuid4().hex[:16]}",
            order_id=order.broker_order_id,
            symbol=order.symbol,
            quantity=fill_quantity,
            price=market_price,
            fees=fill_quantity * fee_per_contract,
            occurred_at=self._now(),
        )
        order.fills.append(fill)
        order.filled_quantity += fill_quantity
        order.remaining_quantity -= fill_quantity
        order.updated_at = self._now()
        order.status = (
            FillStatus.FILLED
            if order.remaining_quantity == 0
            else FillStatus.PARTIAL
        )

        signed_quantity = (
            fill_quantity if order.side == "BUY" else -fill_quantity
        )
        position = next(
            (item for item in positions if item.symbol == order.symbol),
            None,
        )
        if position is None:
            position = PaperPosition(
                symbol=order.symbol,
                quantity=0,
                average_price=0.0,
                market_price=market_price,
                market_value=0.0,
                unrealized_pnl=0.0,
                realized_pnl=0.0,
                updated_at=self._now(),
            )
            positions.append(position)

        old_quantity = position.quantity
        new_quantity = old_quantity + signed_quantity

        if old_quantity == 0 or old_quantity * signed_quantity > 0:
            total_cost = (
                abs(old_quantity) * position.average_price
                + abs(signed_quantity) * market_price
            )
            total_quantity = abs(old_quantity) + abs(signed_quantity)
            position.average_price = (
                total_cost / total_quantity if total_quantity else 0.0
            )
        elif abs(signed_quantity) > abs(old_quantity):
            position.average_price = market_price
        elif new_quantity == 0:
            position.average_price = 0.0

        position.quantity = new_quantity
        position.market_price = market_price
        position.market_value = new_quantity * market_price
        position.unrealized_pnl = (
            (market_price - position.average_price) * new_quantity
            if new_quantity
            else 0.0
        )
        position.updated_at = self._now()

        payload["orders"] = [
            item.model_dump(mode="json") for item in orders
        ]
        payload["positions"] = [
            item.model_dump(mode="json") for item in positions
        ]
        self._save(payload)
        return order

    def cancel(self, broker_order_id: str) -> BrokerPaperOrder:
        payload = self._load()
        orders = [
            BrokerPaperOrder.model_validate(item)
            for item in payload.get("orders", [])
        ]
        order = next(
            (item for item in orders if item.broker_order_id == broker_order_id),
            None,
        )
        if order is None:
            raise KeyError(f"Unknown broker paper order: {broker_order_id}")
        if order.status not in {FillStatus.FILLED, FillStatus.REJECTED}:
            order.status = FillStatus.CANCELLED
            order.updated_at = self._now()
        payload["orders"] = [item.model_dump(mode="json") for item in orders]
        self._save(payload)
        return order
