from __future__ import annotations

import argparse
import json
from pathlib import Path

from .profile import utc_now_iso
from .repository import PortfolioRiskRepository
from .workflow_service import Milestone37WorkflowService


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Milestone 37 portfolio risk management")
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run")
    run.add_argument("--registry-file", type=Path, default=Path("data/portfolio/m36_portfolio_registry.json"))
    run.add_argument("--output-dir", type=Path, default=Path("reports/m37"))
    resolve = sub.add_parser("resolve-breach")
    resolve.add_argument("--breach-id", required=True)
    resolve.add_argument("--resolution", required=True)
    resolve.add_argument("--output-dir", type=Path, default=Path("reports/m37"))
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.command == "run":
        payload = Milestone37WorkflowService().run(args.registry_file, args.output_dir)
    else:
        repo = PortfolioRiskRepository(
            args.output_dir / "risk_assessment_history.json",
            args.output_dir / "risk_breaches.json",
            args.output_dir / "remediation_actions.json",
        )
        payload = repo.resolve_breach(args.breach_id, args.resolution, utc_now_iso())
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0
