from __future__ import annotations

import argparse
import json
from pathlib import Path

from trading_ai.paper_trading.operational_readiness import (
    OperationalReadinessPolicy,
    OperationalReadinessService,
    render_readiness_html,
    render_readiness_markdown,
    write_controls_csv,
    write_readiness_json,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Milestone 51 Phase 9 operational readiness."
    )
    parser.add_argument("--portfolio-id", default="PAPER-PRIMARY")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument(
        "--phase-reports-json",
        required=True,
        help="JSON mapping phase number to report path.",
    )
    parser.add_argument(
        "--mode",
        choices=("VALIDATE", "READINESS", "ACCEPTANCE_TEST", "FULL"),
        default="FULL",
    )
    parser.add_argument("--require-database-url", action="store_true")
    parser.add_argument("--require-polygon-key", action="store_true")
    parser.add_argument("--broker-mode", default="PAPER")
    parser.add_argument(
        "--output-json",
        default="reports/m51/phase9/operational_readiness.json",
    )
    parser.add_argument(
        "--output-markdown",
        default="reports/m51/phase9/operational_readiness.md",
    )
    parser.add_argument(
        "--output-html",
        default="reports/m51/phase9/operational_readiness.html",
    )
    parser.add_argument(
        "--output-controls-csv",
        default="reports/m51/phase9/readiness_controls.csv",
    )
    return parser.parse_args()


def load_phase_reports(mapping_path: str) -> dict[int, dict]:
    mapping = json.loads(Path(mapping_path).read_text(encoding="utf-8"))
    reports = {}
    for phase, path in mapping.items():
        report_path = Path(path)
        reports[int(phase)] = json.loads(
            report_path.read_text(encoding="utf-8")
        )
    return reports


def main() -> None:
    args = parse_args()
    reports = load_phase_reports(args.phase_reports_json)
    result = OperationalReadinessService(
        OperationalReadinessPolicy()
    ).execute(
        args.portfolio_id,
        reports,
        repo_root=args.repo_root,
        mode=args.mode,
        require_database_url=args.require_database_url,
        require_polygon_key=args.require_polygon_key,
        broker_mode=args.broker_mode,
    )
    payload = result.to_dict()
    json_path = write_readiness_json(payload, args.output_json)
    markdown_path = Path(args.output_markdown)
    html_path = Path(args.output_html)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    html_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.write_text(
        render_readiness_markdown(payload), encoding="utf-8"
    )
    html_path.write_text(
        render_readiness_html(payload), encoding="utf-8"
    )
    csv_path = write_controls_csv(
        payload["controls"], args.output_controls_csv
    )
    payload["report_paths"] = {
        "json": str(json_path),
        "markdown": str(markdown_path),
        "html": str(html_path),
        "controls_csv": str(csv_path),
    }
    print(json.dumps(payload, indent=2, sort_keys=True, default=str))
    if result.overall_status == "PHASE9_NOT_READY_FOR_PRODUCTION_ACCEPTANCE":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
