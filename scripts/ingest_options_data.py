from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone

from ingestion_split_common import (
    build_args,
    date_from_args,
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
        help="Skip all Institutional Options downstream stages after options ingestion.",
    )
    parser.add_argument(
        "--skip-institutional-strategies",
        action="store_true",
        help="Skip strategy generation for VALIDATED Institutional Options opportunities.",
    )
    parser.add_argument(
        "--skip-institutional-contracts",
        action="store_true",
        help="Skip exact Polygon contract optimization for STRATEGIES_GENERATED opportunities.",
    )
    parser.add_argument(
        "--skip-institutional-decisions",
        action="store_true",
        help="Skip Institutional Decision Snapshot construction.",
    )
    parser.add_argument(
        "--skip-option-valuation",
        action="store_true",
        help=(
            "Skip Milestone 69 option fair-value, mispricing, edge-attribution, "
            "relative-value, and event-intelligence refresh."
        ),
    )
    parser.add_argument(
        "--require-option-valuation",
        action="store_true",
        help=(
            "Fail shared finalization when the Milestone 69 valuation service "
            "encounters an unexpected processing or persistence failure."
        ),
    )
    parser.add_argument(
        "--option-valuation-limit",
        type=int,
        default=None,
        help="Optional maximum executable contract recommendations valued by Milestone 69.",
    )
    parser.add_argument(
        "--require-institutional-options",
        action="store_true",
        help=(
            "Require enabled Institutional Options stages to execute without unexpected "
            "processing, transaction, schema, or service failures. Governed no-trade "
            "outcomes do not fail this gate."
        ),
    )
    parser.add_argument(
        "--require-institutional-options-complete",
        action="store_true",
        help=(
            "Require complete opportunity coverage. Unlike --require-institutional-options, "
            "this also fails on governed no-strategy/no-contract outcomes and missing option data."
        ),
    )
    parser.add_argument(
        "--institutional-options-limit",
        type=int,
        default=None,
        help="Optional maximum opportunities processed by each Institutional Options stage.",
    )
    parser.add_argument("--refresh-trend-intelligence", action="store_true")
    parser.add_argument("--options-domain-lock-file", default="reports/market_ingestion/options_domain_ingestion.lock")
    parser.add_argument("--shared-finalization-lock-file", default="reports/market_ingestion/shared_market_finalization.lock")
    parser.add_argument("--options-lifecycle-report", default="reports/market_ingestion/options_lifecycle_latest.json")
    parser.add_argument("--shared-finalization-report", default="reports/market_ingestion/options_finalization_latest.json")
    return parser


def _run_options_domain(args, instruments) -> tuple[int, bool, bool]:
    from trading_ai.config import settings
    from trading_ai.database import SessionLocal
    from trading_ai.scanner.options_market_data_ingestion import IngestionManifestStore, OptionHistoryIngestionService
    from trading_ai.scanner.options_market_data_ingestion.polygon_snapshot_provider import PolygonOptionChainSnapshotProvider, PolygonSnapshotPolicy
    from trading_ai.scanner.options_market_data_ingestion.serialization import write_ingestion_profile_json

    capture_date = date_from_args(args)
    option_instruments = tuple(i for i in instruments if i.options_eligible)
    option_symbols = tuple(i.canonical_symbol for i in option_instruments)
    manifest = IngestionManifestStore(args.options_manifest)
    failed = 0
    options_refreshed = False

    if args.reuse_options_snapshot:
        core._reuse_options_snapshot(args, manifest)
    else:
        api_key = getattr(settings, "polygon_api_key", None)
        if not api_key:
            raise RuntimeError("POLYGON_API_KEY is not configured")
        snapshot_tickers = {
            i.canonical_symbol: i.options_snapshot_ticker for i in option_instruments
        }
        cycle_id = args.options_snapshot_run_id or (
            "options-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        )
        mode = "FORCE_REBUILD" if args.force_options_refresh else "FRESH"
        if args.force_options_refresh:
            manifest.reset()
        manifest.begin_cycle(
            cycle_id,
            metadata={
                "mode": mode,
                "capture_date": capture_date.isoformat(),
                "minimum_dte": args.options_minimum_dte,
                "maximum_dte": args.options_maximum_dte,
                "symbol_count": len(option_symbols),
            },
        )
        provider = PolygonOptionChainSnapshotProvider(
            str(api_key),
            as_of_date=capture_date,
            policy=PolygonSnapshotPolicy(
                minimum_dte=args.options_minimum_dte,
                maximum_dte=args.options_maximum_dte,
                minimum_open_interest=args.options_minimum_open_interest,
                minimum_volume=args.options_minimum_volume,
                maximum_strike_distance_pct=args.options_maximum_strike_distance_pct,
                requests_per_second=args.polygon_requests_per_second,
            ),
            symbol_resolver=lambda symbol: snapshot_tickers[symbol.strip().upper()],
        )
        with core._exclusive_file_lock(args.options_lock_file):
            session = SessionLocal()
            try:
                profile = OptionHistoryIngestionService(session, provider, manifest_store=manifest).run(
                    symbols=option_symbols,
                    batch_size=args.options_batch_size,
                    resume=True,
                    fail_fast=not args.continue_on_error,
                    manifest_cycle_id=cycle_id,
                )
            finally:
                session.close()
        lineage = None
        if profile.failed_batches == 0 and profile.valid_records > 0:
            lineage = core._publish_fresh_option_lineage(
                symbols=option_symbols,
                capture_date=capture_date,
                snapshot_id=cycle_id,
                snapshot_timestamp=datetime.fromisoformat(profile.completed_at),
            )
        manifest.complete_cycle(
            cycle_id,
            metadata={
                "valid_records": profile.valid_records,
                "inserted_records": profile.inserted_records,
                "updated_records": profile.updated_records,
                "failed_batches": profile.failed_batches,
                "completed_successfully": profile.failed_batches == 0 and lineage is not None,
                "governed_snapshot_id": (lineage or {}).get("snapshot_id"),
                "governed_snapshot_timestamp": (lineage or {}).get("snapshot_timestamp"),
            },
        )
        write_ingestion_profile_json(profile, args.options_report)
        failed += profile.failed_batches
        options_refreshed = profile.failed_batches == 0 and lineage is not None
        print(f"Options snapshot mode: {mode}; cycle={cycle_id}; capture_window={profile.started_at}..{profile.completed_at}")
        print(
            f"Options ingestion: {profile.valid_records} valid, "
            f"{profile.inserted_records} persisted/upserted, "
            f"{profile.failed_batches} failed batches, {profile.resumed_batches} resumed batches"
        )

    dealer_refreshed = False
    if not args.skip_dealer_positioning:
        original_force = args.force_dealer_refresh
        if options_refreshed:
            args.force_dealer_refresh = True
        dealer_failed, dealer_refreshed = core._run_dealer_positioning(
            args, option_symbols, capture_date
        )
        args.force_dealer_refresh = original_force
        failed += dealer_failed
    return failed, options_refreshed, dealer_refreshed


def main(argv=None) -> int:
    raw = list(sys.argv[1:] if argv is None else argv)
    wrapper, passthrough = build_wrapper_parser().parse_known_args(raw)
    if wrapper.help:
        print("Polygon-only options ingestion and all options-derived intelligence.")
        print(build_wrapper_parser().format_help())
        core.build_parser().print_help()
        return 0

    args = build_args(passthrough, scope="options")
    instruments, symbols = resolve_run_context(args)
    started = datetime.now(timezone.utc)
    report: dict[str, object] = {
        "domain": "options",
        "status": "RUNNING",
        "started_at": started.isoformat(),
        "symbols": len(symbols),
    }
    try:
        print("\nOPTIONS DATA INGESTION")
        print("-" * 48)
        with core._exclusive_file_lock(wrapper.options_domain_lock_file):
            failed, options_refreshed, dealer_refreshed = _run_options_domain(args, instruments)
        report.update(
            {
                "failed_batches": failed,
                "options_refreshed": options_refreshed,
                "dealer_refreshed": dealer_refreshed,
                "domain_status": "READY" if failed == 0 else "DEGRADED",
            }
        )
    except Exception as exc:
        report.update({"status": "FAILED", "error": f"{type(exc).__name__}: {exc}"})
        report["completed_at"] = datetime.now(timezone.utc).isoformat()
        write_report(wrapper.options_lifecycle_report, report)
        print(f"Options ingestion failed: {type(exc).__name__}: {exc}")
        return 1

    if wrapper.skip_finalize:
        report["status"] = "DEGRADED" if failed else "READY"
        report["completed_at"] = datetime.now(timezone.utc).isoformat()
        write_report(wrapper.options_lifecycle_report, report)
        print("Shared intelligence finalization skipped by request")
        return 0 if failed == 0 or args.continue_on_error else 1

    finalize_status = finalize_shared_state(
        args,
        symbols=symbols,
        scope="options",
        run_trend=wrapper.refresh_trend_intelligence,
        upstream_refreshed=bool(options_refreshed or dealer_refreshed),
        lock_file=wrapper.shared_finalization_lock_file,
        report_file=wrapper.shared_finalization_report,
        require_success=wrapper.require_finalize,
        advance_institutional_options=not wrapper.skip_institutional_options,
        run_institutional_strategies=not wrapper.skip_institutional_strategies,
        run_institutional_contracts=not wrapper.skip_institutional_contracts,
        run_institutional_decisions=not wrapper.skip_institutional_decisions,
        run_option_valuation=not wrapper.skip_option_valuation,
        option_valuation_limit=wrapper.option_valuation_limit,
        require_option_valuation=wrapper.require_option_valuation,
        institutional_options_limit=wrapper.institutional_options_limit,
        require_institutional_advancement=wrapper.require_institutional_options,
        require_institutional_advancement_complete=(
            wrapper.require_institutional_options_complete
        ),
    )
    report.update(
        {
            "status": "FAILED" if finalize_status else ("DEGRADED" if failed else "READY"),
            "finalization_status": finalize_status,
            "completed_at": datetime.now(timezone.utc).isoformat(),
        }
    )
    write_report(wrapper.options_lifecycle_report, report)
    return finalize_status or (0 if failed == 0 or args.continue_on_error else 1)


if __name__ == "__main__":
    raise SystemExit(main())
