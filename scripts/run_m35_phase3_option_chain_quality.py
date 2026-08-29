from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path

from trading_ai.database import SessionLocal
from trading_ai.scanner.options_market_data_quality_analytics.policy import (
    OptionChainQualityPolicy,
)
from trading_ai.scanner.options_market_data_quality_analytics.reporting import (
    render_console_report,
)
from trading_ai.scanner.options_market_data_quality_analytics.serialization import (
    write_json_atomic,
    write_symbol_csv,
)
from trading_ai.scanner.options_market_data_quality_analytics.service import (
    OptionChainQualityService,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Evaluate option quote quality, liquidity, spread integrity, "
            "IV/Greeks completeness, anomalies, and governance status."
        )
    )
    parser.add_argument("--as-of-date", required=True)
    parser.add_argument(
        "--canonical-csv",
        default="data/universe/us_listed_equities_etfs.csv",
    )
    parser.add_argument(
        "--report-dir",
        default="reports/m35/phase3/option_chain_quality",
    )
    parser.add_argument("--minimum-volume", type=int, default=100)
    parser.add_argument("--minimum-open-interest", type=int, default=100)
    parser.add_argument("--maximum-spread-pct", type=float, default=0.40)
    parser.add_argument("--ready-score", type=float, default=0.72)
    parser.add_argument("--review-score", type=float, default=0.42)
    parser.add_argument(
        "--database-symbols-only",
        action="store_true",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    as_of_date = date.fromisoformat(args.as_of_date)
    report_dir = Path(args.report_dir)

    policy = OptionChainQualityPolicy(
        minimum_volume=args.minimum_volume,
        minimum_open_interest=args.minimum_open_interest,
        maximum_spread_pct=args.maximum_spread_pct,
        ready_overall_score=args.ready_score,
        review_overall_score=args.review_score,
    )

    with SessionLocal() as session:
        service = OptionChainQualityService(session, policy=policy)
        expected_symbols = (
            None
            if args.database_symbols_only
            else service.load_expected_symbols(args.canonical_csv)
        )
        profile = service.run(
            as_of_date=as_of_date,
            expected_symbols=expected_symbols,
        )

    report_dir.mkdir(parents=True, exist_ok=True)
    json_path = write_json_atomic(report_dir / "run.json", profile)
    csv_path = write_symbol_csv(
        report_dir / "symbol_quality_profiles.csv",
        profile,
    )

    print(render_console_report(profile))
    print(f"JSON report           : {json_path}")
    print(f"Symbol profiles       : {csv_path}")


if __name__ == "__main__":
    main()
