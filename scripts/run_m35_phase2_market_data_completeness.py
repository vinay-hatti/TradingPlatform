from __future__ import annotations

import argparse
import csv
from datetime import date
from pathlib import Path

from trading_ai.database import SessionLocal
from trading_ai.scanner.market_data_quality.completeness import (
    MarketDataCompletenessPolicy,
    MarketDataCompletenessService,
    WeekdayTradingCalendar,
)
from trading_ai.scanner.market_data_quality.completeness_serialization import (
    write_completeness_csv,
    write_completeness_json,
)


def load_symbols(path: Path) -> list[str]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames or "symbol" not in {
            name.strip().lower() for name in reader.fieldnames
        }:
            raise ValueError(f"Canonical CSV must contain a symbol column: {path}")
        symbol_key = next(
            name for name in reader.fieldnames if name.strip().lower() == "symbol"
        )
        active_key = next(
            (
                name for name in reader.fieldnames
                if name.strip().lower() == "active"
            ),
            None,
        )
        symbols: list[str] = []
        for row in reader:
            if active_key is not None:
                active = str(row.get(active_key, "")).strip().lower()
                if active and active not in {"1", "true", "yes", "y"}:
                    continue
            symbol = str(row.get(symbol_key, "")).strip().upper()
            if symbol:
                symbols.append(symbol)
    return sorted(set(symbols))


def parse_holidays(raw_values: list[str]) -> tuple[date, ...]:
    return tuple(date.fromisoformat(value) for value in raw_values)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Evaluate canonical-universe price-history completeness."
    )
    parser.add_argument(
        "--canonical-csv",
        default="data/universe/us_listed_equities_etfs.csv",
    )
    parser.add_argument("--as-of-date", default=date.today().isoformat())
    parser.add_argument("--lookback-trading-days", type=int, default=252)
    parser.add_argument(
        "--holiday",
        action="append",
        default=[],
        help="Exchange holiday in YYYY-MM-DD format; repeat as needed.",
    )
    parser.add_argument(
        "--output-directory",
        default="reports/m35/phase2/completeness",
    )
    args = parser.parse_args()

    canonical_path = Path(args.canonical_csv)
    symbols = load_symbols(canonical_path)
    as_of_date = date.fromisoformat(args.as_of_date)
    calendar = WeekdayTradingCalendar(parse_holidays(args.holiday))
    policy = MarketDataCompletenessPolicy(
        lookback_trading_days=args.lookback_trading_days
    )

    session = SessionLocal()
    try:
        service = MarketDataCompletenessService(
            session,
            policy=policy,
            calendar=calendar,
        )
        profile = service.evaluate(symbols, as_of_date=as_of_date)
    finally:
        session.close()

    output = Path(args.output_directory)
    json_path = write_completeness_json(
        profile, output / "market_data_completeness.json"
    )
    csv_path = write_completeness_csv(
        profile, output / "market_data_symbol_completeness.csv"
    )

    print("=" * 65)
    print("Milestone 35 Phase 2 Market Data Completeness")
    print("=" * 65)
    print(f"Canonical Symbols              {profile.canonical_symbol_count:>10}")
    print(f"Evaluated Symbols              {profile.evaluated_symbol_count:>10}")
    print(f"READY Symbols                  {profile.ready_symbol_count:>10}")
    print(f"DEGRADED Symbols               {profile.degraded_symbol_count:>10}")
    print(f"REVIEW Symbols                 {profile.review_symbol_count:>10}")
    print(f"FAILED Symbols                 {profile.failed_symbol_count:>10}")
    print(f"Symbols With Missing Days      {profile.symbols_with_missing_days:>10}")
    print(f"Total Missing Trading Days     {profile.total_missing_trading_days:>10}")
    print(f"Symbols With Duplicates        {profile.symbols_with_duplicates:>10}")
    print(f"Total Duplicate Rows           {profile.total_duplicate_rows:>10}")
    print(f"Non-Trading-Date Symbols       {profile.symbols_with_non_trading_rows:>10}")
    print(f"Average Continuity             {profile.average_continuity_percentage:>9.2f}%")
    print(f"Minimum Continuity             {profile.minimum_continuity_percentage:>9.2f}%")
    print(f"Completeness Status            {profile.status.value:>10}")
    print(f"JSON Report                    {json_path}")
    print(f"Symbol CSV                     {csv_path}")


if __name__ == "__main__":
    main()
