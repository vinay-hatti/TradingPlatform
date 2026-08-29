from __future__ import annotations

import argparse
import json
from pathlib import Path

from trading_ai.order_management.order_management_reporting import (
    OrderManagementOperationalReport,
)


def read_json(path: str | None, default=None):
    if not path:
        return default
    target = Path(path)
    if not target.exists():
        return default
    return json.loads(target.read_text(encoding="utf-8"))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build the Milestone 30 Phase 4 order-management report."
    )
    parser.add_argument("--aggregates-json", default=None)
    parser.add_argument("--workflow-json", default=None)
    parser.add_argument("--replay-json", default=None)
    parser.add_argument("--audit-json", default=None)
    parser.add_argument("--groups-json", default=None)
    parser.add_argument("--recovery-json", default=None)
    parser.add_argument(
        "--output",
        default="reports/order_management_operational_report.html",
    )
    args = parser.parse_args()

    path = OrderManagementOperationalReport().generate(
        aggregates=read_json(args.aggregates_json, ()),
        workflow_results=read_json(args.workflow_json, ()),
        journal_replays=read_json(args.replay_json, ()),
        audit_status=read_json(args.audit_json, None),
        order_groups=read_json(args.groups_json, ()),
        recovery_checkpoints=read_json(args.recovery_json, ()),
        path=args.output,
    )
    print(f"Order-management operational report: {path}")


if __name__ == "__main__":
    main()
