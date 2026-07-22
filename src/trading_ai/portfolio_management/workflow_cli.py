from __future__ import annotations

import argparse
import json
from pathlib import Path

from .reporting_service import PortfolioPhaseReportingService
from .workflow_service import PortfolioPhaseWorkflowService


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Milestone 36 Phase 1 unified portfolio workflow")
    p.add_argument("--registry-file", type=Path, default=Path("data/portfolio/m36_portfolio_registry.json"))
    p.add_argument("--intake-file", type=Path, default=Path("data/portfolio/m36_portfolio_intake.json"))
    p.add_argument("--lifecycle-file", type=Path, default=Path("data/portfolio/m36_position_lifecycle.json"))
    p.add_argument("--snapshot-directory", type=Path, default=Path("data/portfolio/snapshots"))
    p.add_argument("--exposure-file", type=Path, default=Path("reports/m36/phase1/portfolio_exposure.json"))
    p.add_argument("--audit-file", type=Path, default=Path("data/portfolio/m36_portfolio_audit_history.json"))
    p.add_argument("--database-report-file", type=Path, default=Path("reports/m36/phase1/database_sync.json"))
    p.add_argument("--report-json-file", type=Path, default=Path("reports/m36/phase1/phase1_closure.json"))
    p.add_argument("--report-html-file", type=Path, default=Path("reports/m36/phase1/phase1_closure.html"))
    sub = p.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run")
    run.add_argument("--dashboard-dir", type=Path, default=Path("reports/m35/phase5/dashboard"))
    run.add_argument("--no-auto-repair", action="store_true")
    run.add_argument("--skip-database-sync", action="store_true")
    sub.add_parser("report")
    return p


def main(argv: list[str] | None = None) -> int:
    a = build_parser().parse_args(argv)
    common = dict(registry_file=a.registry_file, snapshot_directory=a.snapshot_directory,
                  exposure_file=a.exposure_file, audit_file=a.audit_file,
                  lifecycle_file=a.lifecycle_file, database_report_file=a.database_report_file)
    if a.command == "report":
        payload = PortfolioPhaseReportingService(**common).write_report(a.report_json_file, a.report_html_file).to_dict()
    else:
        payload = PortfolioPhaseWorkflowService(
            registry_file=a.registry_file, intake_file=a.intake_file,
            lifecycle_file=a.lifecycle_file, snapshot_directory=a.snapshot_directory,
            exposure_file=a.exposure_file, audit_file=a.audit_file,
            database_report_file=a.database_report_file,
            report_json_file=a.report_json_file, report_html_file=a.report_html_file,
        ).run(a.dashboard_dir, auto_repair=not a.no_auto_repair,
              sync_database=not a.skip_database_sync)
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0
