from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path

from trading_ai.database import SessionLocal
from trading_ai.scanner.options_market_data_coverage.policy import (
    OptionChainCoveragePolicy,
)
from trading_ai.scanner.options_market_data_coverage.reporting import (
    render_console_report,
)
from trading_ai.scanner.options_market_data_coverage.serialization import (
    write_expiration_csv,
    write_json_atomic,
    write_symbol_csv,
)
from trading_ai.scanner.options_market_data_coverage.service import (
    OptionChainCoverageService,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Evaluate option-chain coverage, expiration completeness, "
            "strike surfaces, call/put balance, and governance status."
        )
    )
    parser.add_argument("--as-of-date", required=True)
    parser.add_argument(
        "--canonical-csv",
        default="data/universe/us_listed_equities_etfs.csv",
    )
    parser.add_argument(
        "--report-dir",
        default="reports/m35/phase3/option_chain_coverage",
    )
    parser.add_argument("--minimum-contracts", type=int, default=20)
    parser.add_argument("--review-contracts", type=int, default=10)
    parser.add_argument("--minimum-expirations", type=int, default=2)
    parser.add_argument("--review-expirations", type=int, default=1)
    parser.add_argument("--minimum-strikes", type=int, default=5)
    parser.add_argument("--ready-score", type=float, default=0.75)
    parser.add_argument("--review-score", type=float, default=0.45)
    parser.add_argument(
        "--database-symbols-only",
        action="store_true",
        help="Do not add zero-coverage profiles for canonical symbols.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    as_of_date = date.fromisoformat(args.as_of_date)
    report_dir = Path(args.report_dir)

    policy = OptionChainCoveragePolicy(
        minimum_contracts_per_symbol=args.minimum_contracts,
        review_contracts_per_symbol=args.review_contracts,
        minimum_expirations_per_symbol=args.minimum_expirations,
        review_expirations_per_symbol=args.review_expirations,
        minimum_strikes_per_expiration=args.minimum_strikes,
        ready_overall_score=args.ready_score,
        review_overall_score=args.review_score,
    )

    with SessionLocal() as session:
        service = OptionChainCoverageService(session, policy=policy)
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
    symbol_csv = write_symbol_csv(report_dir / "symbol_profiles.csv", profile)
    expiration_csv = write_expiration_csv(
        report_dir / "expiration_profiles.csv",
        profile,
    )

    print(render_console_report(profile))
    print(f"JSON report           : {json_path}")
    print(f"Symbol profiles       : {symbol_csv}")
    print(f"Expiration profiles   : {expiration_csv}")


if __name__ == "__main__":
    main()
