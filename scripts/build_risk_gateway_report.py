from __future__ import annotations

import argparse
import json
from pathlib import Path

from trading_ai.risk_gateway.risk_gateway_reporting import (
    RiskGatewayOperationalReport,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build the Milestone 30 Phase 5 risk-gateway report."
    )
    parser.add_argument(
        "--decisions-json",
        default="reports/risk_gateway_decisions.json",
    )
    parser.add_argument(
        "--output",
        default="reports/risk_gateway_operational_report.html",
    )
    args = parser.parse_args()

    decisions_path = Path(args.decisions_json)
    decisions = ()
    if decisions_path.exists():
        payload = json.loads(decisions_path.read_text(encoding="utf-8"))
        decisions = payload.get("decisions", payload)

    path = RiskGatewayOperationalReport().generate(
        decisions=decisions,
        path=args.output,
    )
    print(f"Risk-gateway operational report: {path}")


if __name__ == "__main__":
    main()
