from __future__ import annotations

import argparse
import json
from pathlib import Path

from trading_ai.paper_trading.automation_control_plane import (
    AutomationControlPlanePolicy,
    AutomationControlPlaneService,
    render_control_plane_markdown,
    write_control_plane_report,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Milestone 51 Phase 5 automation control plane."
    )
    parser.add_argument("--portfolio-id", default="PAPER-PRIMARY")
    parser.add_argument("--phase1-report", required=True)
    parser.add_argument("--phase2-report", required=True)
    parser.add_argument("--phase3-report", required=True)
    parser.add_argument("--phase4-report", required=True)
    parser.add_argument(
        "--mode",
        choices=("DRY_RUN", "SUBMIT", "MONITOR_ONLY"),
        default="DRY_RUN",
    )
    parser.add_argument("--confirmation", default="")
    parser.add_argument("--kill-switch-active", action="store_true")
    parser.add_argument("--disable-paper-routing", action="store_true")
    parser.add_argument(
        "--output-json",
        default="reports/m51/phase5/automation_control_plane.json",
    )
    parser.add_argument(
        "--output-markdown",
        default="reports/m51/phase5/automation_control_plane.md",
    )
    return parser.parse_args()


def read_json(path: str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def main() -> None:
    args = parse_args()
    reports = {
        1: read_json(args.phase1_report),
        2: read_json(args.phase2_report),
        3: read_json(args.phase3_report),
        4: read_json(args.phase4_report),
    }
    policy = AutomationControlPlanePolicy(
        kill_switch_active=args.kill_switch_active,
        paper_routing_enabled=not args.disable_paper_routing,
    )
    result = AutomationControlPlaneService(policy).execute(
        args.portfolio_id,
        reports,
        mode=args.mode,
        confirmation=args.confirmation,
    )
    payload = result.to_dict()
    json_path = write_control_plane_report(payload, args.output_json)
    markdown_path = Path(args.output_markdown)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.write_text(
        render_control_plane_markdown(payload),
        encoding="utf-8",
    )
    payload["report_paths"] = {
        "json": str(json_path),
        "markdown": str(markdown_path),
    }
    print(json.dumps(payload, indent=2, sort_keys=True, default=str))
    if result.status == "PHASE5_AUTOMATION_BLOCKED":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
