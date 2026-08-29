from __future__ import annotations

import argparse
import json
from pathlib import Path

from trading_ai.broker.broker_operational_reporting import (
    BrokerOperationalReport,
)


def read_json(path: str | None):
    if not path:
        return None
    target = Path(path)
    if not target.exists():
        return None
    return json.loads(target.read_text(encoding="utf-8"))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build the Milestone 30 Phase 3 broker operational report."
    )
    parser.add_argument("--readiness-json", default=None)
    parser.add_argument("--execution-json", default=None)
    parser.add_argument("--status-json", default=None)
    parser.add_argument("--reconciliation-json", default=None)
    parser.add_argument(
        "--output",
        default="reports/broker_operational_report.html",
    )
    args = parser.parse_args()

    execution = read_json(args.execution_json)
    status = read_json(args.status_json)

    path = BrokerOperationalReport().generate(
        readiness_profile=read_json(args.readiness_json),
        execution_results=execution or (),
        order_summaries=status or (),
        reconciliation_summary=read_json(args.reconciliation_json),
        path=args.output,
    )
    print(f"Broker operational report: {path}")


if __name__ == "__main__":
    main()
