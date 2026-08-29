from __future__ import annotations

import argparse
from pathlib import Path

from trading_ai.database import SessionLocal
from trading_ai.scanner.market_data_quality import MarketDataCoveragePolicy, MarketDataCoverageService


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Evaluate canonical market-data coverage")
    parser.add_argument("--canonical-csv", default="data/universe/us_listed_equities_etfs.csv")
    parser.add_argument("--minimum-history-days", type=int, default=252)
    parser.add_argument("--output-directory", default="reports/m35/phase2/coverage")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    policy = MarketDataCoveragePolicy(minimum_history_days=args.minimum_history_days)
    with SessionLocal() as session:
        service = MarketDataCoverageService(
            session,
            policy=policy,
            canonical_path=args.canonical_csv,
        )
        profile, paths = service.evaluate_and_write(Path(args.output_directory))

    print("=" * 61)
    print("Milestone 35 Phase 2 Market Data Coverage")
    print("=" * 61)
    print(f"Canonical Symbols       {profile.canonical_symbol_count:>12}")
    print(f"Symbols With History    {profile.symbols_with_history:>12}")
    print(f"Symbols Without History {profile.symbols_without_history:>12}")
    print(f"Coverage Percentage     {profile.coverage_percentage:>11.2f}%")
    print(f"Minimum History Met     {profile.symbols_meeting_minimum_history:>12}")
    print(f"Coverage Status         {profile.status.value:>12}")
    print(f"JSON Report             {paths.json_path}")
    print(f"Symbol CSV              {paths.symbol_csv_path}")


if __name__ == "__main__":
    main()
