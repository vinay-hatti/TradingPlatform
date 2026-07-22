from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path

from trading_ai.scanner.option_surface_persistence.contracts import (
    SurfacePersistencePolicy,
)
from trading_ai.scanner.option_surface_persistence.reporting import (
    render_console_report,
)
from trading_ai.scanner.option_surface_persistence.serialization import (
    write_json_atomic,
)
from trading_ai.scanner.option_surface_persistence.service import (
    OptionSurfacePersistenceService,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Persist governed option-surface analytics as stable CSV "
            "artifacts with governance summaries."
        )
    )
    parser.add_argument("--as-of-date", required=True)
    parser.add_argument(
        "--expiration-input",
        default=(
            "reports/m35/phase4/option_surface_analytics/"
            "expiration_surfaces.jsonl"
        ),
    )
    parser.add_argument(
        "--symbol-input",
        default=(
            "reports/m35/phase4/option_surface_analytics/"
            "symbol_surface_profiles.jsonl"
        ),
    )
    parser.add_argument(
        "--output-dir",
        default=(
            "reports/m35/phase4/option_surface_persistence"
        ),
    )
    parser.add_argument(
        "--ready-only",
        action="store_true",
        help="Persist only READY records; REVIEW records are filtered.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    as_of_date = date.fromisoformat(args.as_of_date)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    statuses = ("READY",) if args.ready_only else ("READY", "REVIEW")
    policy = SurfacePersistencePolicy(
        allowed_expiration_statuses=statuses,
        allowed_symbol_statuses=statuses,
    )

    profile = OptionSurfacePersistenceService(policy).run(
        as_of_date=as_of_date,
        expiration_input_path=args.expiration_input,
        symbol_input_path=args.symbol_input,
        expiration_csv_path=(
            output_dir / "expiration_surfaces.csv"
        ),
        symbol_csv_path=(
            output_dir / "symbol_surface_profiles.csv"
        ),
        governance_summary_path=(
            output_dir / "governance_summary.json"
        ),
    )
    run_path = write_json_atomic(output_dir / "run.json", profile)

    print(render_console_report(profile))
    print(f"Run report                 : {run_path}")


if __name__ == "__main__":
    main()
