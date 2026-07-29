from __future__ import annotations

import argparse
import json

from sqlalchemy import text

from trading_ai.database.session import SessionLocal
from trading_ai.trend_intelligence.forecast_service import TrendForecastService


def _database_symbols() -> list[str]:
    with SessionLocal() as session:
        return [
            str(row[0]).upper()
            for row in session.execute(
                text("SELECT DISTINCT symbol FROM price_history ORDER BY symbol")
            )
        ]


def main() -> None:
    parser = argparse.ArgumentParser(description="Populate Milestone 52 trend forecasts.")
    parser.add_argument("--symbols", default="")
    parser.add_argument("--start", default="2025-01-01")
    parser.add_argument("--end", default="2026-07-28")
    parser.add_argument(
        "--report-path",
        default="reports/trend_intelligence/forecasts_latest.json",
    )
    args = parser.parse_args()

    symbols = (
        [item.strip().upper() for item in args.symbols.split(",") if item.strip()]
        if args.symbols
        else _database_symbols()
    )
    result = TrendForecastService(session_factory=SessionLocal).run(
        symbols=symbols,
        start=args.start,
        end=args.end,
        report_path=args.report_path,
    )
    summary_keys = (
        "status",
        "snapshot_timestamp",
        "requested_symbol_count",
        "symbol_count",
        "forecast_count",
        "skipped_count",
        "error_count",
    )
    print(json.dumps({key: result[key] for key in summary_keys}, indent=2))
    print(args.report_path)


if __name__ == "__main__":
    main()
