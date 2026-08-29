from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path

from trading_ai.database import SessionLocal
from trading_ai.scanner.market_data_quality import MarketDataCoverageService


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Evaluate canonical market-data freshness"
    )
    parser.add_argument(
        "--canonical-csv",
        default="data/universe/us_listed_equities_etfs.csv",
    )
    parser.add_argument("--as-of-date", type=date.fromisoformat)
    parser.add_argument(
        "--output-directory",
        default="reports/m35/phase2/freshness",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()

    with SessionLocal() as session:
        service = MarketDataCoverageService(
            session,
            canonical_path=args.canonical_csv,
        )
        profile, paths = service.evaluate_freshness_and_write(
            Path(args.output_directory),
            as_of_date=args.as_of_date,
        )

    print("=" * 61)
    print("Milestone 35 Phase 2 Market Data Freshness")
    print("=" * 61)
    print(f"Canonical Symbols          {profile.canonical_symbol_count:>10}")
    print(f"Symbols With History       {profile.symbols_with_history:>10}")
    print(f"Fresh Symbols              {profile.fresh_symbol_count:>10}")
    print(f"Stale Symbols              {profile.stale_symbol_count:>10}")
    print(f"Missing Symbols            {profile.missing_symbol_count:>10}")
    print(f"Fresh Percentage           {profile.fresh_percentage:>9.2f}%")
    print(f"Expected Latest Date       {profile.expected_latest_trading_date}")
    print(f"Freshness Status           {profile.status.value:>10}")
    print(f"JSON Report                {paths.json_path}")
    print(f"Symbol CSV                 {paths.symbol_csv_path}")


if __name__ == "__main__":
    main()
