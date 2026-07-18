from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from trading_ai.ui.broker.paper_broker_adapter import LocalPaperBrokerAdapter
from trading_ai.ui.models.paper_commands import (
    PaperOrderRecord,
    PaperOrderStatus,
)
from trading_ai.ui.models.paper_execution import (
    FillStatus,
    PaperExecutionState,
    PaperExecutionSummary,
    ReconciliationIssue,
    ReconciliationReport,
)


class PaperExecutionService:
    def __init__(
        self,
        command_state_path: Path | str = "reports/ui/paper_trading_state.json",
        broker: LocalPaperBrokerAdapter | None = None,
    ):
        self.command_state_path = Path(command_state_path)
        self.broker = broker or LocalPaperBrokerAdapter()

    @staticmethod
    def _now():
        return datetime.now(timezone.utc)

    def _load_command_orders(self) -> list[PaperOrderRecord]:
        if not self.command_state_path.exists():
            return []
        payload = json.loads(
            self.command_state_path.read_text(encoding="utf-8")
        )
        return [
            PaperOrderRecord.model_validate(item)
            for item in payload.get("orders", [])
        ]

    def synchronize_orders(
        self,
        market_prices: dict[str, float] | None = None,
    ) -> int:
        market_prices = market_prices or {}
        local_orders = self._load_command_orders()
        submitted = 0
        for order in local_orders:
            if order.environment not in {"PAPER", "SIMULATION"}:
                continue
            if order.status != PaperOrderStatus.ACCEPTED:
                continue
            market_price = (
                market_prices.get(order.symbol)
                or order.limit_price
                or order.estimated_price
            )
            if market_price is None:
                continue
            before = len(self.broker.list_orders())
            self.broker.submit_from_command(order, market_price)
            after = len(self.broker.list_orders())
            if after > before:
                submitted += 1
        return submitted

    def simulate_open_order_fills(
        self,
        market_prices: dict[str, float],
        *,
        max_fill_quantity: int | None = None,
    ) -> int:
        filled = 0
        for order in self.broker.list_orders():
            if order.status not in {FillStatus.PENDING, FillStatus.PARTIAL}:
                continue
            market_price = market_prices.get(order.symbol)
            if market_price is None:
                continue
            before = order.filled_quantity
            updated = self.broker.simulate_fill(
                order.broker_order_id,
                market_price=market_price,
                max_fill_quantity=max_fill_quantity,
            )
            if updated.filled_quantity > before:
                filled += updated.filled_quantity - before
        return filled

    def reconciliation(self) -> ReconciliationReport:
        local_orders = self._load_command_orders()
        broker_orders = self.broker.list_orders()
        broker_positions = self.broker.list_positions()

        issues: list[ReconciliationIssue] = []
        broker_by_client = {
            order.client_order_id: order for order in broker_orders
        }
        matched_orders = 0

        for local in local_orders:
            if local.status not in {
                PaperOrderStatus.ACCEPTED,
                PaperOrderStatus.CANCELLED,
                PaperOrderStatus.REPLACED,
            }:
                continue
            broker = broker_by_client.get(local.order_id)
            if broker is None and local.status == PaperOrderStatus.ACCEPTED:
                issues.append(
                    ReconciliationIssue(
                        issue_type="MISSING_BROKER_ORDER",
                        severity="ERROR",
                        resource_id=local.order_id,
                        detail=(
                            "Accepted paper command has no broker paper order."
                        ),
                    )
                )
            elif broker is not None:
                matched_orders += 1

        for broker in broker_orders:
            if not any(
                local.order_id == broker.client_order_id
                for local in local_orders
            ):
                issues.append(
                    ReconciliationIssue(
                        issue_type="ORPHAN_BROKER_ORDER",
                        severity="WARNING",
                        resource_id=broker.broker_order_id,
                        detail=(
                            "Broker paper order has no matching command record."
                        ),
                    )
                )

        matched_positions = sum(
            1 for position in broker_positions if position.quantity != 0
        )

        return ReconciliationReport(
            generated_at=self._now(),
            local_order_count=len(local_orders),
            broker_order_count=len(broker_orders),
            local_position_count=len(broker_positions),
            broker_position_count=len(broker_positions),
            matched_orders=matched_orders,
            matched_positions=matched_positions,
            issue_count=len(issues),
            issues=issues,
        )

    def state(self) -> PaperExecutionState:
        orders = self.broker.list_orders()
        positions = self.broker.list_positions()
        fills = [
            fill
            for order in orders
            for fill in order.fills
        ]
        reconciliation = self.reconciliation()

        return PaperExecutionState(
            generated_at=self._now(),
            summary=PaperExecutionSummary(
                total_orders=len(orders),
                open_orders=sum(
                    order.status in {
                        FillStatus.PENDING,
                        FillStatus.PARTIAL,
                    }
                    for order in orders
                ),
                total_fills=len(fills),
                total_positions=sum(
                    position.quantity != 0 for position in positions
                ),
                gross_market_value=sum(
                    abs(position.market_value)
                    for position in positions
                ),
                total_unrealized_pnl=sum(
                    position.unrealized_pnl
                    for position in positions
                ),
                reconciliation_status=(
                    "PASS"
                    if reconciliation.issue_count == 0
                    else "WARNING"
                ),
            ),
            orders=orders,
            fills=fills,
            positions=positions,
            reconciliation=reconciliation,
            notices=[
                "Local paper broker adapter only.",
                "No live broker account or live order route is connected.",
                "Fill simulation requires an explicit market price.",
            ],
        )
