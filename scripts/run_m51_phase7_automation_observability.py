from __future__ import annotations

import argparse
import json
from pathlib import Path

from trading_ai.paper_trading.automation_observability import (
    AutomationObservabilityPolicy,
    AutomationObservabilityService,
    render_observability_markdown,
    write_incidents_csv,
    write_observability_json,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Milestone 51 Phase 7 automation observability."
    )
    parser.add_argument("--portfolio-id", default="PAPER-PRIMARY")
    parser.add_argument("--phase5-report", required=True)
    parser.add_argument("--phase6-report", required=True)
    parser.add_argument(
        "--output-json",
        default="reports/m51/phase7/automation_observability.json",
    )
    parser.add_argument(
        "--output-markdown",
        default="reports/m51/phase7/automation_observability.md",
    )
    parser.add_argument(
        "--output-incidents-csv",
        default="reports/m51/phase7/automation_incidents.csv",
    )
    return parser.parse_args()


def read_json(path: str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def main() -> None:
    args = parse_args()
    result = AutomationObservabilityService(
        AutomationObservabilityPolicy()
    ).execute(
        args.portfolio_id,
        read_json(args.phase5_report),
        read_json(args.phase6_report),
    )
    payload = result.to_dict()
    json_path = write_observability_json(payload, args.output_json)
    markdown_path = Path(args.output_markdown)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.write_text(
        render_observability_markdown(payload),
        encoding="utf-8",
    )
    incidents_path = write_incidents_csv(
        payload["incidents"],
        args.output_incidents_csv,
    )
    payload["report_paths"] = {
        "json": str(json_path),
        "markdown": str(markdown_path),
        "incidents_csv": str(incidents_path),
    }
    print(json.dumps(payload, indent=2, sort_keys=True, default=str))
    if result.overall_status == "PHASE7_AUTOMATION_UNHEALTHY":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
