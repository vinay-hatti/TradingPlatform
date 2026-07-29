from __future__ import annotations

import argparse
import json
from datetime import date

from trading_ai.trend_intelligence.forecast_repository import TrendForecastRepository
from trading_ai.trend_intelligence.institutional_repository import InstitutionalTrendRepository


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify persisted forecast and institutional scanner contexts.")
    parser.add_argument("--symbols", default="AAPL,MSFT,AMZN")
    parser.add_argument("--signal", default="CALL", choices=("CALL", "PUT"))
    parser.add_argument("--horizon-days", type=int, default=10)
    parser.add_argument("--reference-date", default=date.today().isoformat())
    args = parser.parse_args()

    forecast = TrendForecastRepository()
    institutional = InstitutionalTrendRepository()
    rows = []
    for raw in args.symbols.split(","):
        symbol = raw.strip().upper()
        if not symbol:
            continue
        rows.append({
            "symbol": symbol,
            "forecast": forecast.scanner_context(
                symbol, args.signal, horizon_days=args.horizon_days,
                maximum_age_days=3, reference_date=args.reference_date,
            ),
            "institutional": institutional.scanner_context(
                symbol, maximum_age_days=3, reference_date=args.reference_date,
            ),
        })
    print(json.dumps(rows, indent=2, default=str))


if __name__ == "__main__":
    main()
