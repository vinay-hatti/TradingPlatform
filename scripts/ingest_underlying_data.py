from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone

from ingestion_split_common import (
    build_args,
    finalize_shared_state,
    resolve_run_context,
    write_report,
)
import run_market_ingestion as core


def build_wrapper_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--help", action="store_true")
    parser.add_argument("--skip-finalize", action="store_true")
    parser.add_argument("--require-finalize", action="store_true")
    parser.add_argument(
        "--skip-institutional-options",
        action="store_true",
        help="Skip materializing eligible Stock Intelligence candidates into Institutional Options opportunities.",
    )
    parser.add_argument(
        "--require-institutional-options",
        action="store_true",
        help="Fail shared finalization when Institutional Options opportunity materialization is unavailable or fails.",
    )
    parser.add_argument("--underlying-domain-lock-file", default="reports/market_ingestion/underlying_ingestion.lock")
    parser.add_argument("--shared-finalization-lock-file", default="reports/market_ingestion/shared_market_finalization.lock")
    parser.add_argument("--underlying-lifecycle-report", default="reports/market_ingestion/underlying_lifecycle_latest.json")
    parser.add_argument("--shared-finalization-report", default="reports/market_ingestion/underlying_finalization_latest.json")
    return parser


def main(argv=None) -> int:
    raw = list(sys.argv[1:] if argv is None else argv)
    wrapper, passthrough = build_wrapper_parser().parse_known_args(raw)
    if wrapper.help:
        print("Polygon-only underlying ingestion and all underlying-derived intelligence.")
        print(build_wrapper_parser().format_help())
        core.build_parser().print_help()
        return 0

    args = build_args(passthrough, scope="underlying")
    # The underlying entry point owns and refreshes all intelligence derived
    # from underlying price history unless explicitly skipped.
    args.force_trend_refresh = True
    args.force_market_overview_refresh = True

    instruments, symbols = resolve_run_context(args)
    started = datetime.now(timezone.utc)
    report: dict[str, object] = {
        "domain": "underlying",
        "status": "RUNNING",
        "started_at": started.isoformat(),
        "symbols": len(symbols),
    }
    failed = 0
    try:
        print("\nUNDERLYING DATA INGESTION")
        print("-" * 48)
        with core._exclusive_file_lock(wrapper.underlying_domain_lock_file):
            failed = core._run_underlying_ingestion(args, instruments)
        report.update({"failed_symbols": failed, "domain_status": "READY" if failed == 0 else "DEGRADED"})
    except Exception as exc:
        report.update({"status": "FAILED", "error": f"{type(exc).__name__}: {exc}"})
        report["completed_at"] = datetime.now(timezone.utc).isoformat()
        write_report(wrapper.underlying_lifecycle_report, report)
        print(f"Underlying ingestion failed: {type(exc).__name__}: {exc}")
        return 1

    if wrapper.skip_finalize:
        report["status"] = "DEGRADED" if failed else "READY"
        report["completed_at"] = datetime.now(timezone.utc).isoformat()
        write_report(wrapper.underlying_lifecycle_report, report)
        print("Shared intelligence finalization skipped by request")
        return 0 if failed == 0 or args.continue_on_error else 1

    finalize_status = finalize_shared_state(
        args,
        symbols=symbols,
        scope="underlying",
        run_trend=True,
        upstream_refreshed=True,
        lock_file=wrapper.shared_finalization_lock_file,
        report_file=wrapper.shared_finalization_report,
        require_success=wrapper.require_finalize,
        materialize_institutional_options=not wrapper.skip_institutional_options,
        require_institutional_options=wrapper.require_institutional_options,
    )
    report.update(
        {
            "status": "FAILED" if finalize_status else ("DEGRADED" if failed else "READY"),
            "finalization_status": finalize_status,
            "completed_at": datetime.now(timezone.utc).isoformat(),
        }
    )
    write_report(wrapper.underlying_lifecycle_report, report)
    return finalize_status or (0 if failed == 0 or args.continue_on_error else 1)


if __name__ == "__main__":
    raise SystemExit(main())
