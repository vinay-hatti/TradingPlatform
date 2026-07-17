from __future__ import annotations

import argparse
from pathlib import Path
from typing import Sequence

from .operational_resilience_dashboard import (
    OperationalResilienceDashboardBuilder,
)
from .operational_resilience_reporting import (
    OperationalResilienceReportBuilder,
)


def _common_paths(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--environment", default="paper")
    parser.add_argument(
        "--health-registry-path",
        default=(
            "data/operational_resilience/"
            "runtime_health_registry.json"
        ),
    )
    parser.add_argument(
        "--resilience-state-path",
        default=(
            "data/operational_resilience/resilience_state.json"
        ),
    )
    parser.add_argument(
        "--recovery-state-path",
        default=(
            "data/operational_resilience/recovery_state.json"
        ),
    )
    parser.add_argument(
        "--watchdog-state-path",
        default=(
            "data/operational_resilience/watchdog_state.json"
        ),
    )


def register_operational_resilience_commands(
    subparsers: argparse._SubParsersAction,
) -> None:
    report = subparsers.add_parser(
        "operational-resilience-report",
        help="Generate the Phase 8 operational resilience HTML report.",
    )
    _common_paths(report)
    report.add_argument(
        "--output",
        default="reports/operational_resilience_report.html",
    )
    report.set_defaults(
        operational_resilience_handler=_handle_report
    )

    dashboard = subparsers.add_parser(
        "operational-resilience-dashboard",
        help="Generate the Phase 8 dashboard JSON payload.",
    )
    _common_paths(dashboard)
    dashboard.add_argument(
        "--output",
        default="reports/operational_resilience_dashboard.json",
    )
    dashboard.set_defaults(
        operational_resilience_handler=_handle_dashboard
    )


def _paths(args: argparse.Namespace) -> dict:
    return {
        "health_registry_path": args.health_registry_path,
        "resilience_state_path": args.resilience_state_path,
        "recovery_state_path": args.recovery_state_path,
        "watchdog_state_path": args.watchdog_state_path,
    }


def _handle_report(args: argparse.Namespace) -> int:
    target = OperationalResilienceReportBuilder().write_report(
        output=args.output,
        environment=args.environment,
        **_paths(args),
    )
    print(f"Operational resilience report written: {target}")
    return 0


def _handle_dashboard(args: argparse.Namespace) -> int:
    target = OperationalResilienceDashboardBuilder().write(
        output=args.output,
        environment=args.environment,
        **_paths(args),
    )
    print(f"Operational resilience dashboard written: {target}")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="operational-resilience",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    register_operational_resilience_commands(subparsers)
    args = parser.parse_args(argv)
    handler = getattr(args, "operational_resilience_handler", None)
    if handler is None:
        parser.error("No operational resilience handler registered.")
    return int(handler(args))


if __name__ == "__main__":
    raise SystemExit(main())
