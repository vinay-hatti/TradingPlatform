from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path

from trading_ai.scanner.option_surface_decision_integration.contracts import (
    SurfaceDecisionPolicy,
)
from trading_ai.scanner.option_surface_decision_integration.reporting import (
    render_console_report,
)
from trading_ai.scanner.option_surface_decision_integration.serialization import (
    write_json_atomic,
)
from trading_ai.scanner.option_surface_decision_integration.service import (
    OptionSurfaceDecisionIntegrationService,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Convert governed option-surface profiles into scanner-ready "
            "decision features."
        )
    )
    parser.add_argument("--as-of-date", required=True)
    parser.add_argument(
        "--symbol-surface-input",
        default=(
            "reports/m35/phase4/option_surface_persistence/"
            "symbol_surface_profiles.csv"
        ),
    )
    parser.add_argument(
        "--output-dir",
        default=(
            "reports/m35/phase4/option_surface_decision_integration"
        ),
    )
    parser.add_argument(
        "--include-review-surfaces",
        action="store_true",
    )
    parser.add_argument(
        "--minimum-open-interest",
        type=int,
        default=1000,
    )
    parser.add_argument(
        "--minimum-volume",
        type=int,
        default=1,
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    statuses = (
        ("READY", "REVIEW")
        if args.include_review_surfaces
        else ("READY",)
    )
    policy = SurfaceDecisionPolicy(
        allowed_surface_statuses=statuses,
        minimum_total_open_interest=args.minimum_open_interest,
        minimum_total_volume=args.minimum_volume,
    )

    profile = OptionSurfaceDecisionIntegrationService(policy).run(
        as_of_date=date.fromisoformat(args.as_of_date),
        symbol_surface_csv_path=args.symbol_surface_input,
        output_path=output_dir / "surface_decision_features.jsonl",
    )
    run_path = write_json_atomic(output_dir / "run.json", profile)

    print(render_console_report(profile))
    print(f"Run report             : {run_path}")


if __name__ == "__main__":
    main()
