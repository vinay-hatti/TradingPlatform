from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path

from trading_ai.scanner.option_surface_analytics.policy import (
    OptionSurfaceAnalyticsPolicy,
)
from trading_ai.scanner.option_surface_analytics.reporting import (
    render_console_report,
)
from trading_ai.scanner.option_surface_analytics.serialization import (
    write_json_atomic,
)
from trading_ai.scanner.option_surface_analytics.service import (
    OptionSurfaceAnalyticsService,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Aggregate governed historical option features into "
            "expiration and symbol volatility surfaces."
        )
    )
    parser.add_argument("--as-of-date", required=True)
    parser.add_argument(
        "--feature-input",
        default=(
            "reports/m35/phase4/"
            "historical_options_feature_store/features.jsonl"
        ),
    )
    parser.add_argument(
        "--output-dir",
        default="reports/m35/phase4/option_surface_analytics",
    )
    parser.add_argument(
        "--include-review-features",
        action="store_true",
    )
    parser.add_argument(
        "--minimum-contracts-per-expiration",
        type=int,
        default=10,
    )
    parser.add_argument(
        "--minimum-strikes-per-expiration",
        type=int,
        default=5,
    )
    parser.add_argument(
        "--minimum-open-interest-per-expiration",
        type=int,
        default=100,
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    as_of_date = date.fromisoformat(args.as_of_date)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    statuses = (
        ("READY", "REVIEW")
        if args.include_review_features
        else ("READY",)
    )

    policy = OptionSurfaceAnalyticsPolicy(
        allowed_feature_statuses=statuses,
        minimum_contracts_per_expiration=(
            args.minimum_contracts_per_expiration
        ),
        minimum_strikes_per_expiration=(
            args.minimum_strikes_per_expiration
        ),
        minimum_open_interest_per_expiration=(
            args.minimum_open_interest_per_expiration
        ),
    )

    profile = OptionSurfaceAnalyticsService(policy).run(
        as_of_date=as_of_date,
        feature_input_path=args.feature_input,
        expiration_output_path=(
            output_dir / "expiration_surfaces.jsonl"
        ),
        symbol_output_path=(
            output_dir / "symbol_surface_profiles.jsonl"
        ),
    )
    run_path = write_json_atomic(output_dir / "run.json", profile)

    print(render_console_report(profile))
    print(f"Run report            : {run_path}")


if __name__ == "__main__":
    main()
