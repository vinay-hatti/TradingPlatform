from __future__ import annotations

import argparse
import json
from pathlib import Path

from trading_ai.paper_trading.automation_scheduler import (
    AutomationRunStateRepository,
    AutomationSchedulerPolicy,
    AutomationSchedulerService,
    ScheduledPhaseCommand,
    render_scheduler_markdown,
    write_scheduler_report,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Milestone 51 Phase 6 scheduled paper automation."
    )
    parser.add_argument("--portfolio-id", default="PAPER-PRIMARY")
    parser.add_argument("--schedule-name", default="DAILY-PAPER-CYCLE")
    parser.add_argument("--run-key", required=True)
    parser.add_argument("--commands-json", required=True)
    parser.add_argument(
        "--mode",
        choices=("DRY_RUN", "MONITOR_ONLY", "SUBMIT"),
        default="DRY_RUN",
    )
    parser.add_argument("--confirmation", default="")
    parser.add_argument("--require-market-window", action="store_true")
    parser.add_argument("--kill-switch-active", action="store_true")
    parser.add_argument(
        "--state-json",
        default="reports/m51/phase6/scheduler_state.json",
    )
    parser.add_argument(
        "--output-json",
        default="reports/m51/phase6/scheduled_run.json",
    )
    parser.add_argument(
        "--output-markdown",
        default="reports/m51/phase6/scheduled_run.md",
    )
    return parser.parse_args()


def load_commands(path: str) -> tuple[ScheduledPhaseCommand, ...]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    rows = payload.get("commands") if isinstance(payload, dict) else payload
    return tuple(
        ScheduledPhaseCommand(
            phase=int(row["phase"]),
            name=str(row["name"]),
            command=tuple(str(value) for value in row["command"]),
            required=bool(row.get("required", True)),
            timeout_seconds=int(row.get("timeout_seconds", 900)),
            retry_limit=int(row.get("retry_limit", 1)),
            enabled=bool(row.get("enabled", True)),
            metadata=dict(row.get("metadata") or {}),
        )
        for row in rows
    )


def main() -> None:
    args = parse_args()
    commands = load_commands(args.commands_json)
    policy = AutomationSchedulerPolicy(
        kill_switch_active=args.kill_switch_active
    )
    repository = AutomationRunStateRepository(args.state_json)
    service = AutomationSchedulerService(repository, policy=policy)
    result = service.execute(
        args.portfolio_id,
        args.schedule_name,
        args.run_key,
        commands,
        mode=args.mode,
        confirmation=args.confirmation,
        require_market_window=args.require_market_window,
    )
    payload = result.to_dict()
    json_path = write_scheduler_report(payload, args.output_json)
    markdown_path = Path(args.output_markdown)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.write_text(
        render_scheduler_markdown(payload),
        encoding="utf-8",
    )
    payload["report_paths"] = {
        "json": str(json_path),
        "markdown": str(markdown_path),
        "state": str(args.state_json),
    }
    print(json.dumps(payload, indent=2, sort_keys=True, default=str))
    if result.status in {
        "PHASE6_SCHEDULED_RUN_BLOCKED",
        "PHASE6_SCHEDULED_RUN_FAILED",
    }:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
