from __future__ import annotations

import argparse
import json
from pathlib import Path

from .lifecycle_service import PositionLifecycleReconciliationService
from .service import PortfolioRegistryService

DEFAULT_REGISTRY = Path("data/portfolio/m36_portfolio_registry.json")
DEFAULT_JOURNAL = Path("data/portfolio/m36_position_lifecycle.json")
DEFAULT_DASHBOARD = Path("reports/m35/phase5/dashboard")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Milestone 36 position lifecycle reconciliation"
    )
    parser.add_argument("--registry-file", type=Path, default=DEFAULT_REGISTRY)
    parser.add_argument("--journal-file", type=Path, default=DEFAULT_JOURNAL)
    parser.add_argument("--no-auto-repair", action="store_true")
    sub = parser.add_subparsers(dest="command", required=True)

    lifecycle = sub.add_parser("reconcile-lifecycle")
    lifecycle.add_argument("--artifact", type=Path, required=True)

    performance = sub.add_parser("reconcile-performance")
    performance.add_argument("--artifact", type=Path, required=True)

    dashboard = sub.add_parser("reconcile-dashboard")
    dashboard.add_argument("--dashboard-dir", type=Path, default=DEFAULT_DASHBOARD)

    sub.add_parser("audit-identity")
    sub.add_parser("show-journal")

    resolve = sub.add_parser("resolve-exception")
    resolve.add_argument("--exception-id", required=True)
    resolve.add_argument("--resolution", required=True)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    service = PositionLifecycleReconciliationService(
        PortfolioRegistryService(args.registry_file), args.journal_file
    )
    auto_repair = not args.no_auto_repair
    if args.command == "reconcile-lifecycle":
        payload = service.reconcile_lifecycle_artifact(
            args.artifact, auto_repair=auto_repair
        ).to_dict()
    elif args.command == "reconcile-performance":
        payload = [item.to_dict() for item in service.reconcile_performance_artifact(
            args.artifact, auto_repair=auto_repair
        )]
    elif args.command == "reconcile-dashboard":
        payload = [item.to_dict() for item in service.reconcile_dashboard_directory(
            args.dashboard_dir, auto_repair=auto_repair
        )]
    elif args.command == "audit-identity":
        payload = [item.to_dict() for item in service.audit_registry_identity()]
    elif args.command == "show-journal":
        payload = service.load_journal().to_dict()
    elif args.command == "resolve-exception":
        payload = service.resolve_exception(
            args.exception_id, args.resolution
        ).to_dict()
    else:  # pragma: no cover
        raise AssertionError(args.command)
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
