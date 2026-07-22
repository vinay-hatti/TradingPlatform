from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Sequence

from .dashboard_workflow_serialization import (
    write_dashboard_workflow_report_atomic,
)
from .dashboard_workflow_service import (
    DashboardWorkflowService,
)


def _load(path: Path | None) -> dict[str, Any] | None:
    if path is None or not path.exists():
        return None
    payload = json.loads(
        path.read_text(encoding="utf-8")
    )
    if not isinstance(payload, dict):
        raise ValueError(
            f"Expected JSON object: {path}"
        )
    return payload


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Milestone 35 Phase 5 Step 12 dashboard "
            "workflow integration and phase closure"
        )
    )

    parser.add_argument("--market-scan-json", type=Path)
    parser.add_argument("--candidate-inspection-json", type=Path)
    parser.add_argument("--option-chain-json", type=Path)
    parser.add_argument("--strategy-comparison-json", type=Path)
    parser.add_argument("--institutional-decision-json", type=Path)
    parser.add_argument("--paper-trade-preparation-json", type=Path)
    parser.add_argument("--paper-trade-lifecycle-json", type=Path)
    parser.add_argument("--performance-json", type=Path)

    parser.add_argument(
        "--output-file",
        type=Path,
        default=Path(
            "reports/m35/phase5/dashboard/"
            "dashboard_workflow_report.json"
        ),
    )
    return parser


def run(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    path_map = {
        "MARKET_SCAN": args.market_scan_json,
        "CANDIDATE_INSPECTION": (
            args.candidate_inspection_json
        ),
        "OPTION_CHAIN": args.option_chain_json,
        "STRATEGY_COMPARISON": (
            args.strategy_comparison_json
        ),
        "INSTITUTIONAL_DECISION": (
            args.institutional_decision_json
        ),
        "PAPER_TRADE_PREPARATION": (
            args.paper_trade_preparation_json
        ),
        "PAPER_TRADE_LIFECYCLE": (
            args.paper_trade_lifecycle_json
        ),
        "PERFORMANCE": args.performance_json,
    }

    artifacts = {
        name: (
            path or Path(),
            _load(path),
        )
        for name, path in path_map.items()
    }

    report = DashboardWorkflowService().build_report(
        artifacts
    )
    write_dashboard_workflow_report_atomic(
        args.output_file,
        report,
    )

    print(
        json.dumps(
            {
                "symbol": report.symbol,
                "direction": report.direction,
                "workflow_status": (
                    report.workflow_status
                ),
                "completed_stages": (
                    report.completed_stages
                ),
                "total_stages": report.total_stages,
                "paper_trade_ready": (
                    report.paper_trade_ready
                ),
                "position_open": report.position_open,
                "performance_available": (
                    report.performance_available
                ),
                "warnings": list(report.warnings),
                "output_json": str(args.output_file),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
