from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path

from trading_ai.scanner.option_surface_phase_closure.reporting import (
    render_console_report,
    write_html_report,
)
from trading_ai.scanner.option_surface_phase_closure.serialization import (
    write_json_atomic,
)
from trading_ai.scanner.option_surface_phase_closure.service import (
    OptionSurfacePhaseClosureService,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run or validate Milestone 35 Phase 4 and create a "
            "consolidated phase-closure report."
        )
    )
    parser.add_argument("--as-of-date", required=True)
    parser.add_argument(
        "--project-root",
        default=".",
    )
    parser.add_argument(
        "--execute-pipeline",
        action="store_true",
        help="Execute Steps 1-4 before validating artifacts.",
    )
    parser.add_argument(
        "--include-review",
        action="store_true",
        help="Use the broader READY+REVIEW research universe.",
    )
    parser.add_argument(
        "--output-dir",
        default="reports/m35/phase4/phase_closure",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    root = Path(args.project_root).resolve()
    output_dir = root / args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    profile = OptionSurfacePhaseClosureService().run(
        as_of_date=date.fromisoformat(args.as_of_date),
        project_root=root,
        execute_pipeline=args.execute_pipeline,
        include_review=args.include_review,
    )

    run_path = write_json_atomic(output_dir / "run.json", profile)
    html_path = write_html_report(
        output_dir / "phase_closure_report.html",
        profile,
    )

    print(render_console_report(profile))
    print(f"Run report           : {run_path}")
    print(f"HTML report          : {html_path}")

    if profile.phase_status == "FAILED":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
