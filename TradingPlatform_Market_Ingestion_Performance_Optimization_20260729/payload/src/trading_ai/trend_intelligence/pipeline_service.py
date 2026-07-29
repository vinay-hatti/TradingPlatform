from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from time import perf_counter
from typing import Iterable

import pandas as pd
from sqlalchemy import text

from trading_ai.database.session import SessionLocal

from .forecast_service import TrendForecastService
from .institutional_service import INDEX_VOLUME_PROXIES, InstitutionalTrendService
from .platform_integration import TrendPlatformIntegrationService
from .service import SECTOR_ETFS, TrendIntelligenceService
from .transition_service import TrendTransitionService


@dataclass(frozen=True)
class TrendPipelineStageResult:
    name: str
    status: str
    duration_seconds: float
    requested_symbol_count: int
    symbol_count: int
    skipped_count: int
    error_count: int
    report_path: str | None = None

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "status": self.status,
            "duration_seconds": round(self.duration_seconds, 3),
            "requested_symbol_count": self.requested_symbol_count,
            "symbol_count": self.symbol_count,
            "skipped_count": self.skipped_count,
            "error_count": self.error_count,
            "report_path": self.report_path,
        }


class TrendIntelligencePipelineService:
    """Run all Trend Intelligence phases in-process from one OHLCV load.

    The individual phase services and standalone scripts remain supported. This
    service only removes repeated interpreter startup and repeated price_history
    scans; calculation engines, persistence repositories, reports, and ordering
    remain unchanged.
    """

    def __init__(self, session_factory=SessionLocal) -> None:
        self.session_factory = session_factory

    @staticmethod
    def _normalize_symbols(symbols: Iterable[str]) -> list[str]:
        return list(dict.fromkeys(str(s).strip().upper() for s in symbols if str(s).strip()))

    def _load_prices(self, symbols: Iterable[str]) -> dict[str, pd.DataFrame]:
        targets = self._normalize_symbols(symbols)
        if not targets:
            return {}
        with self.session_factory() as session:
            rows = [
                dict(row._mapping)
                for row in session.execute(
                    text(
                        """
                        SELECT symbol, date, close, volume
                        FROM price_history
                        WHERE symbol = ANY(:symbols)
                        ORDER BY symbol, date
                        """
                    ),
                    {"symbols": targets},
                )
            ]
        grouped: dict[str, list[dict]] = {}
        for row in rows:
            grouped.setdefault(str(row["symbol"]).upper(), []).append(row)
        output: dict[str, pd.DataFrame] = {}
        for symbol, values in grouped.items():
            frame = pd.DataFrame(values)
            frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
            frame["close"] = pd.to_numeric(frame["close"], errors="coerce")
            frame["volume"] = pd.to_numeric(frame.get("volume"), errors="coerce")
            frame = frame.dropna(subset=["date", "close"]).sort_values("date")
            frame = frame.drop_duplicates(subset=["date"], keep="last")
            output[symbol] = frame.reset_index(drop=True)
        return output

    @staticmethod
    def _date_slice(data: dict[str, pd.DataFrame], start: str, end: str) -> dict[str, pd.DataFrame]:
        start_ts = pd.Timestamp(start)
        end_ts = pd.Timestamp(end)
        output: dict[str, pd.DataFrame] = {}
        for symbol, source in data.items():
            frame = source.copy()
            if frame.empty:
                output[symbol] = frame
                continue
            dates = pd.to_datetime(frame["date"], errors="coerce")
            frame = frame.loc[(dates >= start_ts) & (dates <= end_ts)].copy()
            frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
            frame = frame.dropna(subset=["date", "close"]).sort_values("date")
            output[symbol] = frame.drop_duplicates("date", keep="last").set_index("date")
        return output

    @staticmethod
    def _write_json(path_value: str, payload: dict) -> None:
        path = Path(path_value)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
        temporary.replace(path)

    @staticmethod
    def _stage(name: str, started: float, payload: dict, report_path: str | None) -> TrendPipelineStageResult:
        return TrendPipelineStageResult(
            name=name,
            status=str(payload.get("status", "FAILED")),
            duration_seconds=perf_counter() - started,
            requested_symbol_count=int(payload.get("requested_symbol_count", payload.get("symbol_count", 0)) or 0),
            symbol_count=int(payload.get("symbol_count", 0) or 0),
            skipped_count=int(payload.get("skipped_count", 0) or 0),
            error_count=int(payload.get("error_count", len(payload.get("errors", []))) or 0),
            report_path=report_path,
        )

    def run(
        self,
        *,
        symbols: Iterable[str],
        start: str,
        end: str,
        platform_report: str,
    ) -> dict:
        pipeline_started = perf_counter()
        targets = self._normalize_symbols(symbols)

        base_service = TrendIntelligenceService(session_factory=self.session_factory)
        membership = base_service._membership()
        references = {"SPY", "QQQ", "IWM"}
        references.update(
            membership.get(symbol, ("", ""))[1]
            for symbol in targets
            if membership.get(symbol, ("", ""))[1]
        )
        references.update(INDEX_VOLUME_PROXIES.values())
        all_price_data = self._load_prices(set(targets) | references)
        dated_price_data = self._date_slice(all_price_data, start, end)

        stages: list[TrendPipelineStageResult] = []

        started = perf_counter()
        base = base_service.build(targets, persist=True, price_data=all_price_data)
        base_path = "reports/trend_intelligence/latest.json"
        self._write_json(base_path, base)
        stages.append(self._stage("trend state", started, base, base_path))

        started = perf_counter()
        transitions = TrendTransitionService(session_factory=self.session_factory).build(
            targets, persist=True, price_data=all_price_data
        )
        transition_path = "reports/trend_intelligence/transitions_latest.json"
        self._write_json(transition_path, transitions)
        stages.append(self._stage("trend transitions", started, transitions, transition_path))

        started = perf_counter()
        forecasts = TrendForecastService(session_factory=self.session_factory).run(
            symbols=targets,
            start=start,
            end=end,
            report_path="reports/trend_intelligence/forecasts_latest.json",
            price_data=dated_price_data,
        )
        stages.append(self._stage("trend forecasts", started, forecasts, "reports/trend_intelligence/forecasts_latest.json"))

        started = perf_counter()
        institutional = InstitutionalTrendService(session_factory=self.session_factory).run(
            targets,
            start,
            end,
            "reports/trend_intelligence/institutional_latest.json",
            price_data=dated_price_data,
        )
        stages.append(self._stage("institutional participation", started, institutional, "reports/trend_intelligence/institutional_latest.json"))

        started = perf_counter()
        integration_service = TrendPlatformIntegrationService(session_factory=self.session_factory)
        contexts = integration_service.contexts(targets)
        market_overview = integration_service.market_overview(targets, contexts=contexts)
        platform_payload = {
            "status": market_overview["status"],
            "warnings": market_overview.get("warnings", []),
            "errors": [],
            "market_overview": market_overview,
            "symbols": [context.to_dict() for context in contexts],
        }
        self._write_json(platform_report, platform_payload)
        stages.append(
            TrendPipelineStageResult(
                name="platform context",
                status=str(platform_payload["status"]),
                duration_seconds=perf_counter() - started,
                requested_symbol_count=len(targets),
                symbol_count=len(contexts),
                skipped_count=0,
                error_count=0,
                report_path=platform_report,
            )
        )

        failed = [stage for stage in stages if stage.status == "FAILED" or stage.error_count]
        status = "READY" if not failed else "DEGRADED"
        return {
            "status": status,
            "snapshot_timestamp": datetime.now(timezone.utc).isoformat(),
            "requested_symbol_count": len(targets),
            "loaded_price_symbol_count": len(all_price_data),
            "duration_seconds": round(perf_counter() - pipeline_started, 3),
            "stages": [stage.to_dict() for stage in stages],
        }
