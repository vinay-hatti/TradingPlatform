from __future__ import annotations

import argparse
import json
from pathlib import Path

from trading_ai.database.session import SessionLocal
from trading_ai.trend_intelligence.service import TrendIntelligenceService
from trading_ai.trend_intelligence.transition_service import TrendTransitionService
from trading_ai.trend_intelligence.forecast_service import TrendForecastService
from trading_ai.trend_intelligence.institutional_service import InstitutionalTrendService

INDEX_SYMBOLS = ["SPX", "NDX", "RUT"]


def write_report(name: str, payload: dict) -> None:
    path = Path("reports/trend_intelligence") / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Rebuild index trend intelligence for SPX, NDX, and RUT.")
    parser.add_argument("--start", default="2025-01-01")
    parser.add_argument("--end", required=True)
    args = parser.parse_args()

    base = TrendIntelligenceService().build(INDEX_SYMBOLS, persist=True)
    write_report("index_base_latest.json", base)

    transition = TrendTransitionService().build(INDEX_SYMBOLS, persist=True)
    write_report("index_transitions_latest.json", transition)

    forecast = TrendForecastService(session_factory=SessionLocal).run(
        symbols=INDEX_SYMBOLS,
        start=args.start,
        end=args.end,
        report_path="reports/trend_intelligence/index_forecasts_latest.json",
    )

    institutional = InstitutionalTrendService(session_factory=SessionLocal).run(
        INDEX_SYMBOLS,
        args.start,
        args.end,
        "reports/trend_intelligence/index_institutional_latest.json",
    )

    summary = {
        "base": {k: base.get(k) for k in ("status", "requested_symbol_count", "symbol_count", "skipped_count", "error_count")},
        "transition": {k: transition.get(k) for k in ("status", "requested_symbol_count", "symbol_count", "skipped_count", "error_count")},
        "forecast": {k: forecast.get(k) for k in ("status", "requested_symbol_count", "symbol_count", "forecast_count", "skipped_count", "error_count")},
        "institutional": {k: institutional.get(k) for k in ("status", "requested_symbol_count", "symbol_count", "skipped_count", "error_count")},
    }
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
