from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from .dashboard_artifact_discovery import (
    DashboardArtifactDiscoveryService,
)
from .dashboard_workflow_serialization import (
    write_dashboard_workflow_report_atomic,
)
from .dashboard_workflow_service import (
    DashboardWorkflowService,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Milestone 35 Phase 5 Step 12 dashboard workflow "
            "artifact auto-discovery and phase closure"
        )
    )
    parser.add_argument(
        "--project-root",
        type=Path,
        default=Path("."),
    )
    parser.add_argument(
        "--output-file",
        type=Path,
        default=Path(
            "reports/m35/phase5/dashboard/"
            "dashboard_workflow_report.json"
        ),
    )
    parser.add_argument(
        "--discovery-report-file",
        type=Path,
        default=Path(
            "reports/m35/phase5/dashboard/"
            "dashboard_artifact_discovery.json"
        ),
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
        "--require-complete",
        action="store_true",
        help=(
            "Return exit code 2 when any required stage is missing "
            "or invalid."
        ),
    )
    return parser


def _resolve_output(project_root: Path, path: Path) -> Path:
    return path if path.is_absolute() else project_root / path


def run(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    project_root = args.project_root.resolve()

    explicit_paths = {
        "MARKET_SCAN": args.market_scan_json,
        "CANDIDATE_INSPECTION": args.candidate_inspection_json,
        "OPTION_CHAIN": args.option_chain_json,
        "STRATEGY_COMPARISON": args.strategy_comparison_json,
        "INSTITUTIONAL_DECISION": args.institutional_decision_json,
        "PAPER_TRADE_PREPARATION": args.paper_trade_preparation_json,
        "PAPER_TRADE_LIFECYCLE": args.paper_trade_lifecycle_json,
        "PERFORMANCE": args.performance_json,
    }

    discovery = DashboardArtifactDiscoveryService().discover(
        project_root,
        explicit_paths=explicit_paths,
    )

    artifacts = {
        name: (
            item.path or Path(),
            item.payload,
        )
        for name, item in discovery.items()
    }

    report = DashboardWorkflowService().build_report(artifacts)

    output_file = _resolve_output(
        project_root,
        args.output_file,
    )
    discovery_report_file = _resolve_output(
        project_root,
        args.discovery_report_file,
    )

    write_dashboard_workflow_report_atomic(
        output_file,
        report,
    )

    discovery_report_file.parent.mkdir(
        parents=True,
        exist_ok=True,
    )
    discovery_report_file.write_text(
        json.dumps(
            {
                name: {
                    "selected_path": (
                        str(item.path)
                        if item.path is not None
                        else None
                    ),
                    "valid_payload": item.payload is not None,
                    "candidate_paths": list(item.candidates),
                }
                for name, item in discovery.items()
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    missing_stages = [
        stage.name
        for stage in report.stages
        if stage.status == "MISSING"
    ]
    failed_stages = [
        stage.name
        for stage in report.stages
        if stage.status == "FAILED"
    ]

    print(
        json.dumps(
            {
                "symbol": report.symbol,
                "direction": report.direction,
                "workflow_status": report.workflow_status,
                "completed_stages": report.completed_stages,
                "total_stages": report.total_stages,
                "paper_trade_ready": report.paper_trade_ready,
                "position_open": report.position_open,
                "performance_available": (
                    report.performance_available
                ),
                "missing_stages": missing_stages,
                "failed_stages": failed_stages,
                "selected_artifacts": {
                    name: (
                        str(item.path)
                        if item.path is not None
                        else None
                    )
                    for name, item in discovery.items()
                },
                "warnings": list(report.warnings),
                "output_json": str(output_file),
                "discovery_report_json": str(
                    discovery_report_file
                ),
            },
            indent=2,
        )
    )

    if args.require_complete and report.workflow_status != "COMPLETE":
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
