from __future__ import annotations

import argparse
import json
from pathlib import Path

from .ingestion_service import PortfolioArtifactIngestionService
from .service import PortfolioRegistryService

DEFAULT_REGISTRY = Path("data/portfolio/m36_portfolio_registry.json")
DEFAULT_INTAKE = Path("data/portfolio/m36_portfolio_intake.json")
DEFAULT_DASHBOARD = Path("reports/m35/phase5/dashboard")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Milestone 36 portfolio artifact ingestion"
    )
    parser.add_argument("--registry-file", type=Path, default=DEFAULT_REGISTRY)
    parser.add_argument("--intake-file", type=Path, default=DEFAULT_INTAKE)
    sub = parser.add_subparsers(dest="command", required=True)

    decision = sub.add_parser("ingest-decision")
    decision.add_argument("--artifact", type=Path, required=True)

    lifecycle = sub.add_parser("ingest-lifecycle")
    lifecycle.add_argument("--artifact", type=Path, required=True)

    performance = sub.add_parser("ingest-performance")
    performance.add_argument("--artifact", type=Path, required=True)

    dashboard = sub.add_parser("ingest-dashboard")
    dashboard.add_argument("--dashboard-dir", type=Path, default=DEFAULT_DASHBOARD)

    sub.add_parser("show-intake")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    registry = PortfolioRegistryService(args.registry_file)
    service = PortfolioArtifactIngestionService(registry, args.intake_file)

    if args.command == "ingest-decision":
        payload = service.ingest_institutional_decision(args.artifact).to_dict()
    elif args.command == "ingest-lifecycle":
        payload = service.ingest_paper_trade_lifecycle(args.artifact).to_dict()
    elif args.command == "ingest-performance":
        payload = [item.to_dict() for item in service.ingest_performance(args.artifact)]
    elif args.command == "ingest-dashboard":
        payload = [
            item.to_dict()
            for item in service.ingest_dashboard_directory(args.dashboard_dir)
        ]
    elif args.command == "show-intake":
        payload = service.load_intake().to_dict()
    else:  # pragma: no cover
        raise AssertionError(args.command)

    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
