from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path

from trading_ai.scanner.options_market_data_readiness.policy import (
    OptionDataReadinessPolicy,
)
from trading_ai.scanner.options_market_data_readiness.reporting import (
    render_console_report,
)
from trading_ai.scanner.options_market_data_readiness.serialization import (
    write_json_atomic,
    write_symbol_csv,
)
from trading_ai.scanner.options_market_data_readiness.service import (
    OptionDataReadinessService,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Combine option-chain coverage and quality governance into "
            "consolidated option-data readiness."
        )
    )
    parser.add_argument("--as-of-date", required=True)
    parser.add_argument(
        "--coverage-report",
        default=(
            "reports/m35/phase3/option_chain_coverage/run.json"
        ),
    )
    parser.add_argument(
        "--quality-report",
        default=(
            "reports/m35/phase3/option_chain_quality/run.json"
        ),
    )
    parser.add_argument(
        "--report-dir",
        default="reports/m35/phase3/readiness",
    )
    parser.add_argument("--coverage-weight", type=float, default=0.50)
    parser.add_argument("--quality-weight", type=float, default=0.50)
    parser.add_argument("--ready-score", type=float, default=0.75)
    parser.add_argument("--review-score", type=float, default=0.45)
    parser.add_argument("--minimum-ready-contracts", type=int, default=10)
    parser.add_argument("--minimum-ready-expirations", type=int, default=1)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    as_of_date = date.fromisoformat(args.as_of_date)
    report_dir = Path(args.report_dir)

    policy = OptionDataReadinessPolicy(
        coverage_weight=args.coverage_weight,
        quality_weight=args.quality_weight,
        ready_score=args.ready_score,
        review_score=args.review_score,
        require_minimum_contracts_for_ready=(
            args.minimum_ready_contracts
        ),
        require_minimum_expirations_for_ready=(
            args.minimum_ready_expirations
        ),
    )

    profile = OptionDataReadinessService(policy=policy).run(
        as_of_date=as_of_date,
        coverage_report_path=args.coverage_report,
        quality_report_path=args.quality_report,
    )

    report_dir.mkdir(parents=True, exist_ok=True)
    json_path = write_json_atomic(report_dir / "run.json", profile)
    csv_path = write_symbol_csv(
        report_dir / "symbol_readiness_profiles.csv",
        profile,
    )

    print(render_console_report(profile))
    print(f"JSON report           : {json_path}")
    print(f"Symbol profiles       : {csv_path}")


if __name__ == "__main__":
    main()
