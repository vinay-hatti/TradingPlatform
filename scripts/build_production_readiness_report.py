from __future__ import annotations

import argparse
from pathlib import Path

from trading_ai.config.production_readiness_reporting import (
    ProductionReadinessReport,
)
from trading_ai.config.startup_readiness_service import StartupReadinessService


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build the Milestone 30 Phase 1 production readiness report."
    )
    parser.add_argument("--environment", default=None)
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--base-file", default="config/runtime.json")
    parser.add_argument(
        "--output",
        default="reports/production_readiness.html",
    )
    parser.add_argument(
        "--allow-blocked-exit-zero",
        action="store_true",
    )
    args = parser.parse_args()

    profile = StartupReadinessService(
        project_root=Path(args.project_root),
    ).evaluate(
        environment=args.environment,
        base_file=args.base_file,
    )
    path = ProductionReadinessReport().generate(profile, args.output)
    print(f"Production readiness report: {path}")
    print(f"Decision: {profile.recommendation}")
    print(f"Score: {profile.score:.2f}")

    if not profile.allowed and not args.allow_blocked_exit_zero:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
