from __future__ import annotations

import argparse
import json
from pathlib import Path

from trading_ai.paper_trading.automation_recovery import (
    AutomationRecoveryPolicy,
    AutomationRecoveryService,
    render_recovery_markdown,
    write_recovery_report,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Milestone 51 Phase 8 paper automation recovery."
    )
    parser.add_argument("--portfolio-id", default="PAPER-PRIMARY")
    parser.add_argument("--scheduler-report", required=True)
    parser.add_argument("--observability-report")
    parser.add_argument("--commands-json")
    parser.add_argument(
        "--mode", choices=("ANALYZE", "RECOVER"), default="ANALYZE"
    )
    parser.add_argument("--confirmation", default="")
    parser.add_argument("--kill-switch-active", action="store_true")
    parser.add_argument(
        "--output-json",
        default="reports/m51/phase8/automation_recovery.json",
    )
    parser.add_argument(
        "--output-markdown",
        default="reports/m51/phase8/automation_recovery.md",
    )
    return parser.parse_args()


def read_json(path: str | None) -> dict | None:
    if not path:
        return None
    return json.loads(Path(path).read_text(encoding="utf-8"))


def read_commands(path: str | None) -> dict[int, tuple[str, ...]]:
    payload = read_json(path)
    if not payload:
        return {}
    rows = payload.get("commands") if isinstance(payload, dict) else payload
    return {
        int(row["phase"]): tuple(str(value) for value in row["command"])
        for row in rows
    }


def main() -> None:
    args = parse_args()
    policy = AutomationRecoveryPolicy(
        kill_switch_active=args.kill_switch_active
    )
    result = AutomationRecoveryService(policy).execute(
        args.portfolio_id,
        read_json(args.scheduler_report) or {},
        mode=args.mode,
        confirmation=args.confirmation,
        phase_commands=read_commands(args.commands_json),
        observability_report=read_json(args.observability_report),
    )
    payload = result.to_dict()
    json_path = write_recovery_report(payload, args.output_json)
    markdown_path = Path(args.output_markdown)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.write_text(
        render_recovery_markdown(payload),
        encoding="utf-8",
    )
    payload["report_paths"] = {
        "json": str(json_path),
        "markdown": str(markdown_path),
    }
    print(json.dumps(payload, indent=2, sort_keys=True, default=str))
    if result.status == "PHASE8_RECOVERY_BLOCKED":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
