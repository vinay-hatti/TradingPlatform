from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

import pandas as pd
from sqlalchemy import text

from trading_ai.database.session import SessionLocal

from .forecast_engine import TrendForecastEngine
from .forecast_repository import TrendForecastRepository


class TrendForecastService:
    """Populate governed trend forecasts from persisted underlying OHLCV data.

    Phase 3 is intentionally database-only, matching the established Milestone 52
    Phase 1/2 population path. No provider calls or MarketService adapter behavior
    are required during forecast generation.
    """

    def __init__(
        self,
        session_factory=SessionLocal,
        engine: TrendForecastEngine | None = None,
        repository: TrendForecastRepository | None = None,
    ) -> None:
        self.session_factory = session_factory
        self.engine = engine or TrendForecastEngine()
        self.repository = repository or TrendForecastRepository(session_factory=session_factory)

    @staticmethod
    def _normalize_symbols(symbols: Iterable[str]) -> list[str]:
        return list(dict.fromkeys(str(symbol).strip().upper() for symbol in symbols if str(symbol).strip()))

    def _load_prices(self, symbols: Iterable[str], start: str, end: str) -> dict[str, pd.DataFrame]:
        targets = self._normalize_symbols(symbols)
        if not targets:
            return {}

        sql = text(
            """
            SELECT symbol, date, close, volume
            FROM price_history
            WHERE symbol = ANY(:symbols)
              AND date >= CAST(:start AS date)
              AND date <= CAST(:end AS date)
            ORDER BY symbol, date
            """
        )
        with self.session_factory() as session:
            rows = [
                dict(row._mapping)
                for row in session.execute(
                    sql,
                    {"symbols": targets, "start": start, "end": end},
                )
            ]

        grouped: dict[str, list[dict]] = {}
        for row in rows:
            grouped.setdefault(str(row["symbol"]).upper(), []).append(row)

        result: dict[str, pd.DataFrame] = {}
        for symbol, values in grouped.items():
            frame = pd.DataFrame(values)
            frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
            frame["close"] = pd.to_numeric(frame["close"], errors="coerce")
            frame["volume"] = pd.to_numeric(frame.get("volume"), errors="coerce")
            frame = frame.dropna(subset=["date", "close"]).sort_values("date")
            frame = frame.drop_duplicates(subset=["date"], keep="last").set_index("date")
            result[symbol] = frame
        return result

    def run(
        self,
        symbols: Iterable[str],
        start: str,
        end: str,
        report_path: str = "reports/trend_intelligence/forecasts_latest.json",
    ) -> dict:
        targets = self._normalize_symbols(symbols)
        data = self._load_prices(targets, start, end)
        results: list[dict] = []
        skipped: list[dict] = []
        errors: list[dict] = []

        for symbol in targets:
            prices = data.get(symbol, pd.DataFrame())
            try:
                symbol_snapshots = [
                    self.engine.calculate(symbol, prices, horizon)
                    for horizon in self.engine.policy.horizons
                ]
                for snapshot in symbol_snapshots:
                    self.repository.save(snapshot)
                    results.append(snapshot.to_dict())
            except ValueError as exc:
                skipped.append(
                    {
                        "symbol": symbol,
                        "reason": "INSUFFICIENT_FORECAST_HISTORY",
                        "detail": str(exc),
                        "available_rows": int(len(prices)),
                    }
                )
            except Exception as exc:
                errors.append(
                    {
                        "symbol": symbol,
                        "error_type": type(exc).__name__,
                        "error": str(exc),
                    }
                )

        if results and not errors:
            status = "READY"
        elif results:
            status = "DEGRADED"
        else:
            status = "FAILED"

        payload = {
            "status": status,
            "snapshot_timestamp": datetime.now(timezone.utc).isoformat(),
            "requested_symbol_count": len(targets),
            "symbol_count": len({item["symbol"] for item in results}),
            "forecast_count": len(results),
            "skipped_count": len(skipped),
            "error_count": len(errors),
            "start_date": start,
            "end_date": end,
            "results": results,
            "skipped": skipped,
            "errors": errors,
        }
        path = Path(report_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return payload
