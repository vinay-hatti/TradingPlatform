from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from time import perf_counter

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
    dealer_refreshed = False

    if args.reuse_options_snapshot:
        core._reuse_options_snapshot(args, manifest)
        if not args.skip_dealer_positioning:
            dealer_failed, dealer_refreshed = core._run_dealer_positioning(
                args, option_symbols, capture_date
            )
            failed += dealer_failed
        return failed, options_refreshed, dealer_refreshed

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
            "lineage_mode": "EXACT_CURRENT_CYCLE",
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
            network_workers=max(1, int(getattr(args, "polygon_network_workers", 4))),
        ),
        symbol_resolver=lambda symbol: snapshot_tickers[symbol.strip().upper()],
    )

    cycle_started = perf_counter()
    building = core._begin_fresh_option_lineage(
        symbols=option_symbols,
        capture_date=capture_date,
        snapshot_id=cycle_id,
        snapshot_timestamp=datetime.now(timezone.utc),
    )
    capture_started = perf_counter()
    with core._exclusive_file_lock(args.options_lock_file):
        session = SessionLocal()
        try:
            profile = OptionHistoryIngestionService(
                session,
                provider,
                manifest_store=manifest,
                governed_snapshot_run_id=int(building["run_id"]),
                governed_snapshot_timestamp=building["snapshot_timestamp"],
            ).run(
                symbols=option_symbols,
                batch_size=args.options_batch_size,
                resume=True,
                fail_fast=not args.continue_on_error,
                manifest_cycle_id=cycle_id,
            )
        finally:
            session.close()
    capture_seconds = perf_counter() - capture_started

    lineage = None
    derived_wall_seconds = 0.0
    volatility_result: dict[str, object] = {}
    liquidity_result: dict[str, object] = {}
    dealer_seconds = 0.0
    dealer_failed = 0

    if profile.failed_batches == 0:
        finalize_started = perf_counter()
        lineage = core._finalize_fresh_option_lineage(
            symbols=option_symbols,
            capture_date=capture_date,
            snapshot_id=cycle_id,
            snapshot_timestamp=datetime.fromisoformat(profile.completed_at),
        )
        finalize_seconds = perf_counter() - finalize_started

        derived = core._run_fresh_option_derived_lanes(
            args,
            snapshot_id=cycle_id,
            capture_date=capture_date,
            symbols=option_symbols,
        )
        volatility_result = dict(derived["volatility"])
        liquidity_result = dict(derived["liquidity"])
        dealer_failed = int(derived["dealer_failed"] or 0)
        dealer_refreshed = bool(derived["dealer_refreshed"])
        dealer_seconds = float(derived["dealer_seconds"] or 0)
        derived_wall_seconds = float(derived["wall_seconds"] or 0)

        volatility_rows = int(volatility_result.get("rows_written", 0) or 0)
        liquidity_rows = int(liquidity_result.get("rows_written", 0) or 0)
        lineage.update(
            {
                "option_rows": int(lineage.get("rows_written", 0) or 0),
                "volatility_rows": volatility_rows,
                "liquidity_rows": liquidity_rows,
            }
        )
        options_refreshed = True
        failed += dealer_failed

        print(
            "Governed option lineage: "
            f"snapshot={lineage['snapshot_id']}, timestamp={lineage['snapshot_timestamp']}, "
            f"contracts={lineage['option_rows']}, volatility={volatility_rows}, "
            f"liquidity={liquidity_rows}, completeness={lineage['completeness_score']}, "
            f"stale_daily_rows_pruned={lineage.get('stale_daily_rows_pruned', 0)}"
        )
    else:
        finalize_seconds = 0.0

    total_seconds = perf_counter() - cycle_started
    polygon_profile = dict(getattr(provider, "performance_profile", {}) or {})
    performance = {
        "capture_seconds": round(capture_seconds, 4),
        "snapshot_finalize_seconds": round(finalize_seconds, 4),
        "derived_parallel_wall_seconds": round(derived_wall_seconds, 4),
        "volatility_seconds": float(volatility_result.get("duration_seconds", 0) or 0),
        "liquidity_seconds": float(liquidity_result.get("duration_seconds", 0) or 0),
        "dealer_seconds": round(dealer_seconds, 4),
        "domain_cycle_seconds": round(total_seconds, 4),
        "dealer_workers": max(1, int(getattr(args, "dealer_positioning_max_workers", 4))),
        "derived_execution_mode": "PARALLEL_3_LANE",
        "polygon_capture": polygon_profile,
    }
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
            "governed_option_rows": (lineage or {}).get("option_rows", 0),
            "governed_volatility_rows": (lineage or {}).get("volatility_rows", 0),
            "governed_liquidity_rows": (lineage or {}).get("liquidity_rows", 0),
            "stale_daily_rows_pruned": (lineage or {}).get("stale_daily_rows_pruned", 0),
            "performance": performance,
        },
    )
    write_ingestion_profile_json(profile, args.options_report)
    failed += profile.failed_batches
    print(f"Options snapshot mode: {mode}; cycle={cycle_id}; capture_window={profile.started_at}..{profile.completed_at}")
    print(
        f"Options ingestion: {profile.valid_records} valid, "
        f"{profile.inserted_records} persisted/upserted, "
        f"{profile.failed_batches} failed batches, {profile.resumed_batches} resumed batches"
    )
    print(
        "Options performance: "
        f"capture={performance['capture_seconds']:.2f}s, "
        f"snapshot_finalize={performance['snapshot_finalize_seconds']:.2f}s, "
        f"derived_parallel_wall={performance['derived_parallel_wall_seconds']:.2f}s "
        f"(volatility={performance['volatility_seconds']:.2f}s, "
        f"liquidity={performance['liquidity_seconds']:.2f}s, "
        f"dealer={performance['dealer_seconds']:.2f}s), "
        f"options_domain={performance['domain_cycle_seconds']:.2f}s"
    )
    if polygon_profile:
        print(
            "Polygon capture profile: "
            f"mode={polygon_profile.get('execution_mode')}, "
            f"workers={polygon_profile.get('network_workers')}, "
            f"global_rps={polygon_profile.get('requests_per_second_limit')}, "
            f"requests={polygon_profile.get('request_count')}, "
            f"aggregate_http={float(polygon_profile.get('aggregate_http_seconds', 0) or 0):.2f}s, "
            f"aggregate_throttle_wait={float(polygon_profile.get('aggregate_throttle_wait_seconds', 0) or 0):.2f}s"
        )
    return failed, options_refreshed, dealer_refreshed


def main(argv=None) -> int:
    wall_started = perf_counter()
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
        report["elapsed_seconds"] = round(perf_counter() - wall_started, 4)
        write_report(wrapper.options_lifecycle_report, report)
        print(f"Options ingestion failed: {type(exc).__name__}: {exc}")
        print(f"Options end-to-end performance: {report['elapsed_seconds']:.2f}s")
        return 1

    if wrapper.skip_finalize:
        report["status"] = "DEGRADED" if failed else "READY"
        report["completed_at"] = datetime.now(timezone.utc).isoformat()
        report["elapsed_seconds"] = round(perf_counter() - wall_started, 4)
        write_report(wrapper.options_lifecycle_report, report)
        print("Shared intelligence finalization skipped by request")
        print(f"Options end-to-end performance: {report['elapsed_seconds']:.2f}s")
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
    downside_risk_veto_refresh = {"status": "SKIPPED"}
    if finalize_status == 0:
        project_root = __import__("pathlib").Path(__file__).resolve().parents[1]
        champion_meta = project_root / "data/downside_risk_veto/champion/DRVE-CHAMPION-001.json"
        if not champion_meta.exists():
            downside_risk_veto_refresh = {"status": "SKIPPED_NO_CHAMPION"}
        else:
            try:
                from trading_ai.downside_risk_veto.live_authority import refresh_live_authority
                refreshed_veto = refresh_live_authority(str(project_root))
                downside_risk_veto_refresh = {
                    "status": "READY",
                    "stock_scanner_run_id": refreshed_veto.get("stock_scanner_run_id"),
                    "market_as_of_date": refreshed_veto.get("market_as_of_date"),
                    "scored_symbol_count": refreshed_veto.get("scored_symbol_count"),
                    "veto_count": refreshed_veto.get("veto_count"),
                    "model_fingerprint": refreshed_veto.get("model_fingerprint"),
                }
                print(
                    "M77.23 downside-risk veto authority: "
                    f"run={refreshed_veto.get('stock_scanner_run_id')}, "
                    f"as_of={refreshed_veto.get('market_as_of_date')}, "
                    f"scored={refreshed_veto.get('scored_symbol_count')}, "
                    f"veto={refreshed_veto.get('veto_count')}"
                )
                try:
                    from trading_ai.downside_risk_veto.monitoring import update_prospective_outcomes
                    prospective = update_prospective_outcomes(str(project_root))
                    downside_risk_veto_refresh["prospective_observation_count"] = (prospective.get("summary") or {}).get("observation_count")
                except Exception as monitor_exc:
                    downside_risk_veto_refresh["prospective_monitoring_warning"] = f"{type(monitor_exc).__name__}: {monitor_exc}"
                try:
                    from trading_ai.research.m77.positive_selection_prospective_shadow import (
                        ShadowConfig,
                        record_shadow_snapshot,
                        write_frozen_protocol,
                    )
                    write_frozen_protocol(project_root)
                    positive_shadow = record_shadow_snapshot(ShadowConfig(project_root=str(project_root)))
                    downside_risk_veto_refresh["positive_selection_shadow"] = positive_shadow
                    print(
                        "M77.24.1 positive-selection shadow: "
                        f"status={positive_shadow.get('status')}, "
                        f"as_of={positive_shadow.get('market_as_of_date')}, "
                        f"candidates={positive_shadow.get('candidate_count', 0)}, "
                        f"selected={positive_shadow.get('selected_count', 0)}"
                    )
                except Exception as shadow_exc:
                    downside_risk_veto_refresh["positive_selection_shadow_warning"] = (
                        f"{type(shadow_exc).__name__}: {shadow_exc}"
                    )
                try:
                    from trading_ai.research.m77.management_geometry_prospective_shadow import (
                        ManagementShadowConfig,
                        record_shadow_snapshot as record_management_geometry_shadow,
                        write_frozen_protocol as write_management_geometry_protocol,
                    )
                    write_management_geometry_protocol(project_root)
                    management_shadow = record_management_geometry_shadow(
                        ManagementShadowConfig(project_root=str(project_root))
                    )
                    downside_risk_veto_refresh["management_geometry_shadow"] = management_shadow
                    print(
                        "M77.26.2 management-geometry shadow: "
                        f"status={management_shadow.get('status')}, "
                        f"as_of={management_shadow.get('market_as_of_date')}, "
                        f"candidates={management_shadow.get('candidate_count', 0)}, "
                        f"atr_ready={management_shadow.get('atr_ready_count', 0)}"
                    )
                except Exception as management_shadow_exc:
                    downside_risk_veto_refresh["management_geometry_shadow_warning"] = (
                        f"{type(management_shadow_exc).__name__}: {management_shadow_exc}"
                    )
                try:
                    from trading_ai.research.m77.candidate_quality_management_interaction_prospective_shadow import (
                        InteractionShadowConfig,
                        record_shadow_snapshot as record_cqmi_shadow,
                        write_frozen_protocol as write_cqmi_protocol,
                    )
                    write_cqmi_protocol(project_root)
                    cqmi_shadow = record_cqmi_shadow(
                        InteractionShadowConfig(project_root=str(project_root))
                    )
                    downside_risk_veto_refresh["candidate_quality_management_interaction_shadow"] = cqmi_shadow
                    print(
                        "M77.27.1 CQMI shadow: "
                        f"status={cqmi_shadow.get('status')}, "
                        f"as_of={cqmi_shadow.get('market_as_of_date')}, "
                        f"eligible={cqmi_shadow.get('eligible_count', 0)}, "
                        f"selected={cqmi_shadow.get('selected_count', 0)}, "
                        f"atr_ready={cqmi_shadow.get('atr_ready_count', 0)}"
                    )
                except Exception as cqmi_shadow_exc:
                    downside_risk_veto_refresh["candidate_quality_management_interaction_shadow_warning"] = (
                        f"{type(cqmi_shadow_exc).__name__}: {cqmi_shadow_exc}"
                    )
                try:
                    from trading_ai.research.m77.cross_sectional_capital_priority_prospective_shadow import (
                        CapitalPriorityShadowConfig,
                        record_shadow_snapshot as record_capital_priority_shadow,
                        write_frozen_protocol as write_capital_priority_protocol,
                    )
                    write_capital_priority_protocol(project_root)
                    capital_priority_shadow = record_capital_priority_shadow(
                        CapitalPriorityShadowConfig(project_root=str(project_root))
                    )
                    downside_risk_veto_refresh["cross_sectional_capital_priority_shadow"] = capital_priority_shadow
                    print(
                        "M77.30 CPRE shadow: "
                        f"status={capital_priority_shadow.get('status')}, "
                        f"as_of={capital_priority_shadow.get('market_as_of_date')}, "
                        f"eligible={capital_priority_shadow.get('eligible_count', 0)}, "
                        f"selected={capital_priority_shadow.get('selected_count', 0)}, "
                        f"atr_ready={capital_priority_shadow.get('atr_ready_count', 0)}"
                    )
                except Exception as capital_priority_shadow_exc:
                    downside_risk_veto_refresh["cross_sectional_capital_priority_shadow_warning"] = (
                        f"{type(capital_priority_shadow_exc).__name__}: {capital_priority_shadow_exc}"
                    )
            except Exception as exc:
                downside_risk_veto_refresh = {"status": "FAILED", "error": f"{type(exc).__name__}: {exc}"}
                print(f"M77.23 downside-risk veto authority refresh failed: {type(exc).__name__}: {exc}")

    report.update(
        {
            "status": "FAILED" if finalize_status else ("DEGRADED" if failed else "READY"),
            "finalization_status": finalize_status,
            "downside_risk_veto_refresh": downside_risk_veto_refresh,
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "elapsed_seconds": round(perf_counter() - wall_started, 4),
        }
    )
    write_report(wrapper.options_lifecycle_report, report)
    print(f"Options end-to-end performance: {report['elapsed_seconds']:.2f}s")
    return finalize_status or (0 if failed == 0 or args.continue_on_error else 1)


if __name__ == "__main__":
    raise SystemExit(main())
