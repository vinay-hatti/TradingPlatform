from __future__ import annotations

from typing import Any, Mapping

from .profile import PortfolioPositionInput


class PortfolioInputAdapter:
    def from_payload(
        self,
        lifecycle_report: Mapping[str, Any],
        market_data: Mapping[str, Any],
    ) -> tuple[PortfolioPositionInput, ...]:
        rows = lifecycle_report.get("positions") or ()
        output: list[PortfolioPositionInput] = []
        for row in rows:
            if str(row.get("status", "")).upper() != "OPEN":
                continue
            symbol = str(row.get("symbol") or "").upper()
            if not symbol:
                continue
            metadata = dict(row.get("metadata") or {})
            quote = market_data.get(symbol) or {}
            if not isinstance(quote, Mapping):
                quote = {"price": quote}
            current_price = float(
                quote.get("price")
                or quote.get("last")
                or quote.get("close")
                or 0.0
            )
            quantity = float(row.get("quantity") or 0.0)
            entry = float(row.get("average_entry_price") or 0.0)
            security_type = str(row.get("security_type") or "STK").upper()
            multiplier = float(
                metadata.get("multiplier")
                or (100.0 if security_type in {"OPT", "OPTION"} else 1.0)
            )
            direction = str(row.get("direction") or "LONG").upper()
            sign = 1.0 if direction == "LONG" else -1.0
            market_value = sign * current_price * quantity * multiplier
            unrealized = (
                sign * (current_price - entry) * quantity * multiplier
            )
            output.append(
                PortfolioPositionInput(
                    position_id=str(row.get("position_id") or ""),
                    symbol=symbol,
                    security_type=security_type,
                    direction=direction,
                    quantity=quantity,
                    average_entry_price=entry,
                    current_price=current_price,
                    market_value=market_value,
                    unrealized_pnl=unrealized,
                    sector=str(
                        quote.get("sector")
                        or metadata.get("sector")
                        or "UNKNOWN"
                    ),
                    industry=str(
                        quote.get("industry")
                        or metadata.get("industry")
                        or "UNKNOWN"
                    ),
                    beta=float(quote.get("beta") or metadata.get("beta") or 1.0),
                    delta=float(
                        quote.get("delta") or metadata.get("delta") or 0.0
                    ),
                    gamma=float(
                        quote.get("gamma") or metadata.get("gamma") or 0.0
                    ),
                    theta=float(
                        quote.get("theta") or metadata.get("theta") or 0.0
                    ),
                    vega=float(
                        quote.get("vega") or metadata.get("vega") or 0.0
                    ),
                    rho=float(
                        quote.get("rho") or metadata.get("rho") or 0.0
                    ),
                    multiplier=multiplier,
                    currency=str(row.get("currency") or "USD"),
                    metadata={**metadata, **dict(quote)},
                )
            )
        return tuple(output)
