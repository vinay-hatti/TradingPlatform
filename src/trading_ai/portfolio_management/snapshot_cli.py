from __future__ import annotations

import argparse
import json
from pathlib import Path

from .service import PortfolioRegistryService
from .snapshot_service import PortfolioSnapshotService


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Milestone 36 portfolio snapshot and exposure CLI")
    parser.add_argument("--registry-file", type=Path, default=Path("data/portfolio/m36_portfolio_registry.json"))
    parser.add_argument("--snapshot-dir", type=Path, default=Path("data/portfolio/snapshots"))
    parser.add_argument("--exposure-file", type=Path, default=Path("reports/m36/phase1/portfolio_exposure.json"))
    parser.add_argument("--audit-file", type=Path, default=Path("data/portfolio/m36_portfolio_audit_history.json"))
    sub = parser.add_subparsers(dest="command", required=True)

    create = sub.add_parser("create-snapshot")
    create.add_argument("--event-type", default="PORTFOLIO_SNAPSHOT")
    sub.add_parser("show-exposure")
    sub.add_parser("show-audit")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    registry_service = PortfolioRegistryService(args.registry_file)
    service = PortfolioSnapshotService(
        registry_service=registry_service,
        snapshot_directory=args.snapshot_dir,
        exposure_file=args.exposure_file,
        audit_file=args.audit_file,
    )
    if args.command == "create-snapshot":
        payload = service.create_snapshot(event_type=args.event_type).to_dict()
    elif args.command == "show-exposure":
        payload = service.build_exposure_view().to_dict()
    else:
        payload = service.load_audit_history().to_dict()
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0
