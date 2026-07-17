from __future__ import annotations

from collections import defaultdict
from typing import Iterable

from .broker_status_profile import BrokerFillEvent, BrokerPositionProfile


class BrokerPositionEngine:
    """Build normalized positions from broker fill events."""

    def build_positions(
        self,
        fills: Iterable[BrokerFillEvent],
        *,
        broker: str,
        account_id: str,
        asset_class_by_symbol: dict[str, str] | None = None,
        multiplier_by_symbol: dict[str, int] | None = None,
    ) -> tuple[BrokerPositionProfile, ...]:
        asset_class_by_symbol = asset_class_by_symbol or {}
        multiplier_by_symbol = multiplier_by_symbol or {}

        grouped: dict[str, list[BrokerFillEvent]] = defaultdict(list)
        for fill in fills:
            if fill.account_id == account_id:
                grouped[fill.symbol].append(fill)

        positions: list[BrokerPositionProfile] = []
        for symbol, symbol_fills in grouped.items():
            signed_quantity = 0.0
            signed_cost = 0.0
            realized_pnl = 0.0

            for fill in sorted(
                symbol_fills,
                key=lambda item: item.event_timestamp,
            ):
                side = fill.side.upper()
                direction = -1.0 if side.startswith("SELL") else 1.0
                quantity = direction * fill.quantity
                signed_quantity += quantity
                signed_cost += quantity * fill.price

            average_cost = (
                abs(signed_cost / signed_quantity)
                if signed_quantity != 0
                else 0.0
            )
            positions.append(
                BrokerPositionProfile(
                    broker=broker,
                    account_id=account_id,
                    symbol=symbol,
                    asset_class=asset_class_by_symbol.get(
                        symbol,
                        "OPTION" if len(symbol) > 8 else "EQUITY",
                    ),
                    quantity=signed_quantity,
                    average_cost=average_cost,
                    realized_pnl=realized_pnl,
                    multiplier=multiplier_by_symbol.get(symbol, 1),
                    metadata={"fill_count": len(symbol_fills)},
                )
            )

        return tuple(sorted(positions, key=lambda item: item.symbol))
