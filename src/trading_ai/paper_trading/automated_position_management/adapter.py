from __future__ import annotations

from typing import Any, Mapping

from .profile import ManagedPaperPosition


class LifecyclePositionAdapter:
    def from_report(
        self,
        payload: Mapping[str, Any],
        market_prices: Mapping[str, Any],
    ) -> tuple[ManagedPaperPosition, ...]:
        portfolio_id = str(payload.get("portfolio_id") or "PAPER-PRIMARY")
        rows = payload.get("positions") or ()
        output: list[ManagedPaperPosition] = []
        for row in rows:
            if str(row.get("status", "")).upper() != "OPEN":
                continue
            symbol = str(row.get("symbol", "")).upper()
            if not symbol:
                continue
            metadata = dict(row.get("metadata") or {})
            market = market_prices.get(symbol)
            if isinstance(market, Mapping):
                current_price = float(
                    market.get("price")
                    or market.get("last")
                    or market.get("close")
                    or 0.0
                )
            else:
                current_price = float(market or 0.0)
            output.append(
                ManagedPaperPosition(
                    position_id=str(row["position_id"]),
                    portfolio_id=portfolio_id,
                    aggregate_id=str(row["aggregate_id"]),
                    symbol=symbol,
                    security_type=str(row.get("security_type") or "STK"),
                    direction=str(row.get("direction") or "LONG"),
                    quantity=float(row.get("quantity") or 0.0),
                    average_entry_price=float(
                        row.get("average_entry_price") or 0.0
                    ),
                    current_price=current_price,
                    opened_at=str(row.get("opened_at") or ""),
                    expiry=str(metadata.get("expiry") or ""),
                    strike=metadata.get("strike"),
                    right=str(metadata.get("right") or ""),
                    local_symbol=str(metadata.get("local_symbol") or ""),
                    contract_id=int(metadata.get("contract_id") or 0),
                    currency=str(row.get("currency") or "USD"),
                    sector=str(metadata.get("sector") or "UNKNOWN"),
                    metadata=metadata,
                )
            )
        return tuple(output)
