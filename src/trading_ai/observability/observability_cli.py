from __future__ import annotations
import argparse
from .observability_dashboard import ObservabilityDashboardBuilder
from .observability_reporting import ObservabilityReportBuilder

def _report(args):
    path = ObservabilityReportBuilder().write(args.output)
    print(f"Observability report written: {path}")
    return 0

def _dashboard(args):
    path = ObservabilityDashboardBuilder().write(args.output)
    print(f"Observability dashboard written: {path}")
    return 0

def register_observability_commands(subparsers):
    report = subparsers.add_parser("observability-report")
    report.add_argument("--output", default="reports/observability_report.html")
    report.set_defaults(func=_report)
    dashboard = subparsers.add_parser("observability-dashboard")
    dashboard.add_argument("--output", default="reports/observability_dashboard.json")
    dashboard.set_defaults(func=_dashboard)

def main(argv=None):
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    register_observability_commands(subparsers)
    args = parser.parse_args(argv)
    return int(args.func(args))

if __name__ == "__main__":
    raise SystemExit(main())
