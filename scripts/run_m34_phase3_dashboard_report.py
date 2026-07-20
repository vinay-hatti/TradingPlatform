from __future__ import annotations

import argparse
import importlib
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from trading_ai.research_workstation.phase3_dashboard import (
    Phase3DashboardEngine,
    write_phase3_dashboard_html,
    write_phase3_dashboard_json,
)


def _namespace(value: Any) -> Any:
    if isinstance(value, dict):
        return SimpleNamespace(
            **{key: _namespace(item) for key, item in value.items()}
        )
    if isinstance(value, list):
        return tuple(_namespace(item) for item in value)
    return value


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Generate the Milestone 34 Phase 3 dashboard from "
            "serialized component payloads."
        )
    )
    parser.add_argument("--trade-id", required=True)
    parser.add_argument("--symbol", required=True)
    parser.add_argument("--strategy-name", required=True)
    parser.add_argument("--trade-construction-json", required=True)
    parser.add_argument("--portfolio-allocation-json", required=True)
    parser.add_argument("--lifecycle-json", required=True)
    parser.add_argument("--governance-json", required=True)
    parser.add_argument(
        "--output-dir",
        default="reports/m34/phase3",
    )
    args = parser.parse_args()

    def load(path: str) -> Any:
        return _namespace(
            json.loads(Path(path).read_text(encoding="utf-8"))
        )

    profile = Phase3DashboardEngine().build(
        trade_id=args.trade_id,
        symbol=args.symbol,
        strategy_name=args.strategy_name,
        trade_construction=load(args.trade_construction_json),
        portfolio_allocation=load(args.portfolio_allocation_json),
        lifecycle=load(args.lifecycle_json),
        governance=load(args.governance_json),
    )

    output_dir = Path(args.output_dir)
    json_path = write_phase3_dashboard_json(
        profile,
        output_dir / "phase3_dashboard.json",
    )
    html_path = write_phase3_dashboard_html(
        profile,
        output_dir / "phase3_dashboard.html",
    )

    print(f"JSON report: {json_path}")
    print(f"HTML report: {html_path}")
    print(f"Overall status: {profile.overall_status}")
    print(f"Execution allowed: {profile.execution_allowed}")


if __name__ == "__main__":
    main()
