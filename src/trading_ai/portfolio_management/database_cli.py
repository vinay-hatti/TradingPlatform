from __future__ import annotations

import argparse
import json
from pathlib import Path

from .database_service import PortfolioDatabaseSyncService


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Milestone 36 portfolio database synchronization")
    parser.add_argument("--registry-file", type=Path, default=Path("data/portfolio/m36_portfolio_registry.json"))
    parser.add_argument("--snapshot-directory", type=Path, default=Path("data/portfolio/snapshots"))
    parser.add_argument("--audit-file", type=Path, default=Path("data/portfolio/m36_portfolio_audit_history.json"))
    parser.add_argument("--report-file", type=Path, default=Path("reports/m36/phase1/database_sync.json"))
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("sync")
    validate = sub.add_parser("validate")
    validate.add_argument("--portfolio-id", default="PRIMARY")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    service = PortfolioDatabaseSyncService()
    if args.command == "sync":
        payload = service.synchronize(registry_file=args.registry_file, snapshot_directory=args.snapshot_directory, audit_file=args.audit_file, report_file=args.report_file)
    else:
        payload = service.validate(args.portfolio_id.upper())
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0
