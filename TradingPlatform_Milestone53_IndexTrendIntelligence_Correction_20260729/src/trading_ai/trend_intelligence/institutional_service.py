from __future__ import annotations

import json
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

import pandas as pd
from sqlalchemy import text

from trading_ai.database.session import SessionLocal

from .institutional_aggregation import build_institutional_market_overview
from .institutional_engine import InstitutionalTrendEngine
from .institutional_repository import InstitutionalTrendRepository


INDEX_VOLUME_PROXIES = {"SPX": "SPY", "NDX": "QQQ", "RUT": "IWM"}


class InstitutionalTrendService:
    def __init__(self, session_factory=SessionLocal, engine=None, repository=None) -> None:
        self.session_factory = session_factory
        self.engine = engine or InstitutionalTrendEngine()
        self.repository = repository or InstitutionalTrendRepository(session_factory=session_factory)

    @staticmethod
    def _normalize_symbols(symbols: Iterable[str]) -> list[str]:
        return list(dict.fromkeys(str(s).strip().upper() for s in symbols if str(s).strip()))

    def _load_prices(self, symbols: list[str], start: str, end: str) -> dict[str, pd.DataFrame]:
        if not symbols:
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
            rows = [dict(r._mapping) for r in session.execute(sql, {"symbols": symbols, "start": start, "end": end})]
        grouped: dict[str, list[dict]] = {}
        for row in rows:
            grouped.setdefault(str(row["symbol"]).upper(), []).append(row)
        result: dict[str, pd.DataFrame] = {}
        for symbol, values in grouped.items():
            frame = pd.DataFrame(values)
            frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
            frame["close"] = pd.to_numeric(frame["close"], errors="coerce")
            frame["volume"] = pd.to_numeric(frame["volume"], errors="coerce")
            frame = frame.dropna(subset=["date", "close"]).drop_duplicates("date", keep="last")
            result[symbol] = frame.sort_values("date").set_index("date")
        return result

    def run(self, symbols: Iterable[str], start: str, end: str, report_path: str = "reports/trend_intelligence/institutional_latest.json") -> dict:
        targets = self._normalize_symbols(symbols)
        proxy_symbols = [INDEX_VOLUME_PROXIES[s] for s in targets if s in INDEX_VOLUME_PROXIES]
        load_targets = list(dict.fromkeys(targets + ["SPY"] + proxy_symbols))
        data = self._load_prices(load_targets, start, end)
        benchmark = data.get("SPY", pd.DataFrame())
        results: list[dict] = []
        skipped: list[dict] = []
        errors: list[dict] = []
        for symbol in targets:
            prices = data.get(symbol, pd.DataFrame()).copy()
            volume_proxy_symbol = INDEX_VOLUME_PROXIES.get(symbol)
            try:
                if volume_proxy_symbol:
                    proxy = data.get(volume_proxy_symbol, pd.DataFrame())
                    if proxy.empty or "volume" not in proxy.columns:
                        raise ValueError(
                            f"Index volume proxy {volume_proxy_symbol} unavailable for {symbol}."
                        )
                    proxy_volume = pd.to_numeric(proxy["volume"], errors="coerce")
                    prices["volume"] = proxy_volume.reindex(prices.index)
                snapshot = self.engine.calculate(symbol, prices, benchmark=benchmark)
                if volume_proxy_symbol:
                    snapshot = replace(
                        snapshot,
                        warnings=list(snapshot.warnings) + [f"INDEX_VOLUME_PROXY:{volume_proxy_symbol}"],
                        metadata={
                            **dict(snapshot.metadata),
                            "asset_class": "INDEX",
                            "native_volume_applicable": False,
                            "volume_proxy_symbol": volume_proxy_symbol,
                            "volume_proxy_basis": "listed_index_etf_volume",
                        },
                    )
                self.repository.save(snapshot)
                results.append(snapshot.to_dict())
            except ValueError as exc:
                skipped.append({"symbol": symbol, "reason": "INSUFFICIENT_INSTITUTIONAL_HISTORY", "detail": str(exc), "available_rows": len(prices)})
            except Exception as exc:
                errors.append({"symbol": symbol, "error_type": type(exc).__name__, "error": str(exc)})
        status = "READY" if results and not errors else "DEGRADED" if results else "FAILED"
        payload = {
            "status": status,
            "snapshot_timestamp": datetime.now(timezone.utc).isoformat(),
            "requested_symbol_count": len(targets),
            "symbol_count": len(results),
            "skipped_count": len(skipped),
            "error_count": len(errors),
            "start_date": start,
            "end_date": end,
            "market_overview": build_institutional_market_overview(results),
            "results": results,
            "skipped": skipped,
            "errors": errors,
        }
        path = Path(report_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2, allow_nan=False), encoding="utf-8")
        return payload
