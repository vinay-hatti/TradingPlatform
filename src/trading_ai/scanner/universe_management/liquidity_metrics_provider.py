from __future__ import annotations

import csv
from datetime import datetime, timezone
from pathlib import Path

from .liquidity_profile import LiquidityMetrics


def _float(value: str | None) -> float | None:
    if value is None or str(value).strip() == "":
        return None
    return float(value)


def _int(value: str | None) -> int | None:
    number = _float(value)
    return None if number is None else int(number)


def _bool(value: str | None) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "y"}


def _datetime(value: str | None) -> datetime:
    if not value:
        return datetime.now(timezone.utc)
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


class CsvLiquidityMetricsProvider:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def load(self) -> dict[str, LiquidityMetrics]:
        if not self.path.is_file():
            raise FileNotFoundError(f"Liquidity metrics CSV not found: {self.path}")
        results: dict[str, LiquidityMetrics] = {}
        with self.path.open("r", encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle):
                symbol = str(row.get("symbol", "")).strip().upper()
                if not symbol:
                    continue
                results[symbol] = LiquidityMetrics(
                    symbol=symbol,
                    as_of=_datetime(row.get("as_of")),
                    price=_float(row.get("price")),
                    average_daily_volume=_int(row.get("average_daily_volume")),
                    average_daily_dollar_volume=_float(row.get("average_daily_dollar_volume")),
                    bid_ask_spread_pct=_float(row.get("bid_ask_spread_pct")),
                    market_cap=_float(row.get("market_cap")),
                    option_volume=_int(row.get("option_volume")),
                    option_open_interest=_int(row.get("option_open_interest")),
                    halted=_bool(row.get("halted")),
                    metadata={"source": str(self.path)},
                )
        return results
