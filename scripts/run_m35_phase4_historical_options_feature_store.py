from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path

from trading_ai.database import SessionLocal
from trading_ai.scanner.historical_options_feature_store.policy import (
    HistoricalOptionFeaturePolicy,
)
from trading_ai.scanner.historical_options_feature_store.reporting import (
    render_console_report,
)
from trading_ai.scanner.historical_options_feature_store.serialization import (
    write_run_json_atomic,
)
from trading_ai.scanner.historical_options_feature_store.service import (
    HistoricalOptionFeatureService,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Generate readiness-gated historical option feature records."
        )
    )
    parser.add_argument("--as-of-date", required=True)
    parser.add_argument(
        "--readiness-report",
        default="reports/m35/phase3/readiness/run.json",
    )
    parser.add_argument(
        "--output-dir",
        default="reports/m35/phase4/historical_options_feature_store",
    )
    parser.add_argument(
        "--include-review",
        action="store_true",
    )
    parser.add_argument("--minimum-dte", type=int, default=1)
    parser.add_argument("--maximum-dte", type=int, default=365)
    parser.add_argument("--minimum-open-interest", type=int, default=1)
    parser.add_argument("--minimum-volume", type=int, default=0)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    as_of_date = date.fromisoformat(args.as_of_date)
    output_dir = Path(args.output_dir)

    statuses = ("READY", "REVIEW") if args.include_review else ("READY",)

    policy = HistoricalOptionFeaturePolicy(
        allowed_readiness_statuses=statuses,
        minimum_days_to_expiration=args.minimum_dte,
        maximum_days_to_expiration=args.maximum_dte,
        minimum_open_interest=args.minimum_open_interest,
        minimum_volume=args.minimum_volume,
    )

    output_dir.mkdir(parents=True, exist_ok=True)
    feature_path = output_dir / "features.jsonl"

    with SessionLocal() as session:
        profile = HistoricalOptionFeatureService(
            session,
            policy=policy,
        ).run(
            as_of_date=as_of_date,
            readiness_report_path=args.readiness_report,
            output_path=feature_path,
        )

    run_path = write_run_json_atomic(output_dir / "run.json", profile)

    print(render_console_report(profile))
    print(f"Run report            : {run_path}")


if __name__ == "__main__":
    main()
