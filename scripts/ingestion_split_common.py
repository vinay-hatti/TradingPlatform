from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import date, datetime, timezone
from time import perf_counter
from pathlib import Path
from typing import Sequence

import run_market_ingestion as core

_FORBIDDEN = {"--mode", "--data-scope"}


def reject_managed_arguments(argv: Sequence[str]) -> None:
    for token in argv:
        if token.split("=", 1)[0] in _FORBIDDEN:
            raise SystemExit(
                f"{token.split('=', 1)[0]} is owned by the split ingestion entry point."
            )


def build_args(argv: Sequence[str], *, scope: str) -> argparse.Namespace:
    reject_managed_arguments(argv)
    parsed = core.build_parser().parse_args([*argv, "--mode", "daily", "--data-scope", scope])
    parsed = core._apply_mode_preset(parsed)
    parsed = core._validate_option_controls(parsed)
    parsed = core._resolve_force_controls(parsed)
    return parsed


def resolve_run_context(args: argparse.Namespace):
    registry = core.build_registry(args.universe_file, args.index_universe_file)
    instruments = core.resolve_instruments(
        registry, args.symbols, args.symbols_file, args.asset_classes
    )
    symbols = tuple(i.canonical_symbol for i in instruments)
    counts = Counter(i.asset_class for i in instruments)
    print(f"Market ingestion universe: {len(symbols)} canonical instruments")
    print("Asset classes: " + ", ".join(f"{k}={v}" for k, v in sorted(counts.items())))
    for instrument in instruments:
        if instrument.asset_class == "INDEX":
            print(
                f"[INDEX] {instrument.canonical_symbol}: price={instrument.price_ticker}, "
                f"options_snapshot={instrument.options_snapshot_ticker}, "
                f"options_reference={instrument.options_reference_ticker}"
            )
    return instruments, symbols


def write_report(path_value: str, payload: dict) -> None:
    path = Path(path_value)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    tmp.replace(path)



def refresh_inflection_intelligence(*, build_mode: str, required: bool = False) -> dict[str, object]:
    from trading_ai.database.session import SessionLocal
    from trading_ai.inflection_intelligence.service import InstitutionalInflectionService
    try:
        result = InstitutionalInflectionService(SessionLocal).build(build_mode=build_mode)
        diagnostics = result.get("diagnostics") or {}
        classes = diagnostics.get("classifications") or {}
        print(
            "Institutional Inflection Intelligence: "
            f"status={result.get('status')}, mode={build_mode}, built={result.get('built', 0)}, "
            f"average={result.get('average_score', 0)}, high_conviction={result.get('high_conviction', 0)}, "
            f"actionable={classes.get('ACTIONABLE', 0)}, watch={classes.get('WATCH', 0)}"
        )
        return result
    except Exception as exc:
        print(f"Institutional Inflection Intelligence failed: {type(exc).__name__}: {exc}")
        if required:
            raise
        return {"status": "FAILED", "build_mode": build_mode, "error": f"{type(exc).__name__}: {exc}"}



def refresh_option_valuation_intelligence(
    *,
    required: bool = False,
    limit: int | None = None,
    opportunity_ids: tuple[str, ...] | list[str] | None = None,
    scope: str = "CURRENT_RUN",
) -> dict[str, object]:
    from trading_ai.database.session import SessionLocal
    from trading_ai.option_valuation_intelligence.service import InstitutionalOptionValuationService
    try:
        result = InstitutionalOptionValuationService(SessionLocal).build(
            limit=limit, opportunity_ids=opportunity_ids, scope=scope
        )
        print(
            "Option Valuation Intelligence: "
            f"status={result.get('status')}, built={result.get('built', 0)}, "
            f"underpriced={result.get('underpriced', 0)}, overpriced={result.get('overpriced', 0)}, "
            f"average_edge_score={result.get('average_edge_score', 0)}, "
            f"scope={result.get('scope')}, duration={result.get('duration_seconds', 0)}s, "
            f"rate={result.get('valuations_per_second', 0)}/s"
        )
        return result
    except Exception as exc:
        print(f"Option Valuation Intelligence failed: {type(exc).__name__}: {exc}")
        if required:
            raise
        return {"status": "FAILED", "error": f"{type(exc).__name__}: {exc}"}



def refresh_futures_intelligence(*, required: bool = False) -> dict[str, object]:
    import os
    from datetime import date, timedelta
    from trading_ai.database.session import SessionLocal
    from trading_ai.futures_intelligence.service import FuturesIntelligenceService
    enabled = str(os.getenv("TRADING_AI_FUTURES_AUTO_INGEST", "true")).strip().lower() not in {"0","false","no","off"}
    try:
        svc = FuturesIntelligenceService(SessionLocal)
        if enabled:
            lookback = max(1, int(os.getenv("TRADING_AI_FUTURES_LOOKBACK_DAYS", "3")))
            end = date.today(); start = end - timedelta(days=lookback)
            result = svc.ingest(("ES","NQ","RTY"), start.isoformat(), end.isoformat(), ("1min","1session"), int(os.getenv("TRADING_AI_FUTURES_MIN_DTM", "5")))
            print("Futures Intelligence: status=READY, provider=POLYGON_FUTURES, products=ES,NQ,RTY")
            return result
        result = svc.refresh(("ES","NQ","RTY"))
        print(f"Futures Intelligence: auto_ingest=disabled, status={result.get('status')}")
        return result
    except Exception as exc:
        print(f"Futures Intelligence failed: {type(exc).__name__}: {exc}")
        if required:
            raise
        return {"status":"FAILED","error":f"{type(exc).__name__}: {exc}"}


def refresh_opex_intelligence(*, required: bool = False) -> dict[str, object]:
    from trading_ai.database.session import SessionLocal
    from trading_ai.opex_intelligence.service import OpexIntelligenceService
    try:
        result = OpexIntelligenceService(SessionLocal).refresh(cycles=3)
        print(
            "OPEX Intelligence: "
            f"status={result.get('status')}, built={result.get('built', 0)}, "
            f"symbols={','.join(result.get('symbols', []))}, cycles={result.get('cycles', 0)}"
        )
        return result
    except Exception as exc:
        print(f"OPEX Intelligence failed: {type(exc).__name__}: {exc}")
        if required:
            raise
        return {"status":"FAILED","error":f"{type(exc).__name__}: {exc}"}


def materialize_institutional_options_opportunities(
    *,
    publication_name: str,
) -> dict[str, object]:
    """Idempotently materialize eligible Stock Intelligence candidates.

    This stage intentionally stops at the Institutional Options opportunity and
    thesis domains. Strategy generation, exact-contract optimization, valuation,
    and decision construction remain owned by the options-data workflow because
    they require a current persisted Polygon option snapshot.
    """
    from trading_ai.database.session import SessionLocal
    from trading_ai.institutional_options.opportunity_ingestion import (
        InstitutionalOpportunityIngestionService,
    )

    with SessionLocal() as session:
        try:
            result = InstitutionalOpportunityIngestionService(session).ingest(
                publication_name=publication_name,
            )
            session.commit()
        except Exception:
            session.rollback()
            raise

    payload = dict(result.__dict__)
    print(
        "Institutional Options materialization: "
        f"publication={payload.get('publication_name')}, "
        f"run_id={payload.get('stock_scanner_run_id')}, "
        f"requested={payload.get('requested', 0)}, "
        f"discovered={payload.get('discovered', 0)}, "
        f"validated={payload.get('validated', 0)}, "
        f"rejected={payload.get('rejected', 0)}, "
        f"existing={payload.get('existing', 0)}, "
        f"refreshed={payload.get('refreshed', 0)}, "
        f"existing_rejected={payload.get('existing_rejected', 0)}"
    )
    return payload



def finalize_shared_state(
    args: argparse.Namespace,
    *,
    symbols: tuple[str, ...],
    scope: str,
    run_trend: bool,
    upstream_refreshed: bool,
    lock_file: str,
    report_file: str,
    require_success: bool,
    materialize_institutional_options: bool = False,
    require_institutional_options: bool = False,
    advance_institutional_options: bool = False,
    run_institutional_strategies: bool = True,
    run_institutional_contracts: bool = True,
    run_institutional_decisions: bool = True,
    run_option_valuation: bool = True,
    option_valuation_limit: int | None = None,
    require_option_valuation: bool = False,
    institutional_options_limit: int | None = None,
    require_institutional_advancement: bool = False,
    require_institutional_advancement_complete: bool = False,
) -> int:
    started = datetime.now(timezone.utc)
    report: dict[str, object] = {
        "scope": scope,
        "status": "RUNNING",
        "started_at": started.isoformat(),
        "symbols": len(symbols),
        "trend_requested": run_trend,
        "lock_file": lock_file,
    }
    try:
        with core._exclusive_file_lock(lock_file):
            print("\nSHARED INTELLIGENCE FINALIZATION")
            print("-" * 48)
            trend_refreshed = False
            if run_trend:
                # Split underlying ingestion is authoritative for every
                # underlying-derived trend phase. Force flags remain governed by
                # the core implementation but this stage is never hidden behind
                # a cloned core.main() invocation.
                trend_refreshed = core._run_trend_intelligence_pipeline(args, symbols)
            else:
                print("Trend Intelligence: reused latest persisted publication")

            overview_refreshed = False
            if not args.skip_market_overview:
                overview_refreshed = core._run_market_overview(
                    args, upstream_refreshed=upstream_refreshed
                )
            else:
                print("Market Overview: skipped by request")

            market_intelligence_refreshed = False
            if not args.skip_market_intelligence:
                market_intelligence_refreshed = core._run_market_intelligence(args)
            else:
                print("Market Intelligence: skipped by request")

            publication = None
            if not args.skip_publication:
                publication = core._publish_scanner_state(args)
                if not publication.scanner_ready:
                    raise RuntimeError("Published market state is not scanner-ready")
            else:
                print("Market-state publication: skipped by request")

            stock_publication = None
            if not args.skip_stock_intelligence:
                stock_publication = core._publish_stock_intelligence(args, symbols)
                usable = stock_publication and stock_publication.get("status") in {"READY", "DEGRADED"}
                if args.require_stock_intelligence and not usable:
                    raise RuntimeError("No usable Stock Intelligence publication was produced")
            else:
                print("Stock Intelligence publication: skipped by request")

            inflection_intelligence = None
            if stock_publication and stock_publication.get("status") in {"READY", "DEGRADED"}:
                inflection_intelligence = refresh_inflection_intelligence(
                    build_mode="UNDERLYING_PRIMARY" if scope == "underlying" else "OPTIONS_ENRICHMENT",
                    required=require_success,
                )

            institutional_options = None
            if materialize_institutional_options:
                usable = stock_publication and stock_publication.get("status") in {"READY", "DEGRADED"}
                if usable:
                    try:
                        institutional_options = materialize_institutional_options_opportunities(
                            publication_name=args.stock_intelligence_publication_name,
                        )
                    except Exception as exc:
                        institutional_options = {
                            "status": "FAILED",
                            "error": f"{type(exc).__name__}: {exc}",
                            "publication_name": args.stock_intelligence_publication_name,
                        }
                        print(
                            "Institutional Options materialization failed: "
                            f"{type(exc).__name__}: {exc}"
                        )
                        if require_institutional_options:
                            raise RuntimeError(
                                "Institutional Options opportunity materialization failed"
                            ) from exc
                else:
                    institutional_options = {
                        "status": "SKIPPED",
                        "reason": "NO_USABLE_STOCK_INTELLIGENCE_PUBLICATION",
                        "publication_name": args.stock_intelligence_publication_name,
                    }
                    print(
                        "Institutional Options materialization: skipped because no usable "
                        "Stock Intelligence publication was produced"
                    )
                    if require_institutional_options:
                        raise RuntimeError(
                            "Institutional Options materialization requires a usable Stock Intelligence publication"
                        )
            else:
                print("Institutional Options materialization: not executed (underlying ingestion owns opportunity creation)")

            institutional_options_advancement = None
            if advance_institutional_options:
                institutional_options_advancement = advance_institutional_options_workflow(
                    run_strategies=run_institutional_strategies,
                    run_contracts=run_institutional_contracts,
                    run_decisions=run_institutional_decisions,
                    run_option_valuation=run_option_valuation,
                    option_valuation_limit=option_valuation_limit,
                    require_option_valuation=require_option_valuation,
                    limit=institutional_options_limit,
                    require_success=require_institutional_advancement,
                    require_complete=require_institutional_advancement_complete,
                )
            else:
                print("Institutional Options downstream advancement: skipped by request")

            option_valuation_intelligence = None
            if institutional_options_advancement is not None:
                option_valuation_intelligence = (
                    institutional_options_advancement.get("stages", {}).get("option_valuation")
                )

            # M71.2: refresh futures confirmation first, then update the OPEX posterior.
            futures_intelligence = refresh_futures_intelligence(required=False)
            opex_intelligence = refresh_opex_intelligence(required=False)

            report.update(
                {
                    "status": "READY",
                    "trend_refreshed": trend_refreshed,
                    "market_overview_refreshed": overview_refreshed,
                    "market_intelligence_refreshed": market_intelligence_refreshed,
                    "market_publication": None if publication is None else args.publication_name,
                    "scanner_ready": None if publication is None else bool(publication.scanner_ready),
                    "stock_publication": stock_publication,
                    "inflection_intelligence": inflection_intelligence,
                    "institutional_options": institutional_options,
                    "institutional_options_advancement": institutional_options_advancement,
                    "option_valuation_intelligence": option_valuation_intelligence,
                    "futures_intelligence": futures_intelligence,
                    "opex_intelligence": opex_intelligence,
                }
            )
    except Exception as exc:
        report.update({"status": "FAILED", "error": f"{type(exc).__name__}: {exc}"})
        print(f"Shared intelligence finalization failed: {type(exc).__name__}: {exc}")
        if require_success:
            report["completed_at"] = datetime.now(timezone.utc).isoformat()
            write_report(report_file, report)
            return 1
    report["completed_at"] = datetime.now(timezone.utc).isoformat()
    write_report(report_file, report)
    print(f"Shared intelligence finalization: status={report['status']}; report={report_file}")
    return 0


def advance_institutional_options_workflow(
    *,
    run_strategies: bool = True,
    run_contracts: bool = True,
    run_decisions: bool = True,
    run_option_valuation: bool = True,
    option_valuation_limit: int | None = None,
    require_option_valuation: bool = False,
    limit: int | None = None,
    require_success: bool = False,
    require_complete: bool = False,
) -> dict[str, object]:
    """Advance materialized Institutional Options opportunities.

    Opportunity creation remains owned by underlying ingestion. The options
    workflow classifies expected governance outcomes separately from genuine
    processing failures so a healthy daily pipeline is not failed merely
    because an opportunity has no eligible strategy or executable contract.
    """
    from trading_ai.database.session import SessionLocal
    from trading_ai.institutional_options.contract_optimization import (
        InstitutionalContractOptimizationService,
    )
    from trading_ai.institutional_options.decision import InstitutionalDecisionService
    from trading_ai.institutional_options.strategy_generation import (
        InstitutionalStrategyGenerationService,
    )
    from trading_ai.institutional_options.publication_scope import latest_opportunity_ids

    stages: dict[str, object] = {}
    unexpected_failures: list[str] = []
    completeness_failures: list[str] = []
    with SessionLocal() as scope_session:
        stock_scanner_run_id, scoped_opportunity_ids = latest_opportunity_ids(scope_session)

    stages["scope"] = {
        "publication_name": "current_stock_intelligence",
        "stock_scanner_run_id": stock_scanner_run_id,
        "opportunity_count": len(scoped_opportunity_ids),
        "mode": "LATEST_PUBLICATION",
    }
    print(
        "Institutional Options advancement scope: "
        f"publication=current_stock_intelligence, run_id={stock_scanner_run_id}, "
        f"opportunities={len(scoped_opportunity_ids)}"
    )

    summary = {
        "strategies_generated": 0,
        "governed_no_strategy": 0,
        "contracts_optimized": 0,
        "governed_no_contract": 0,
        "missing_option_data": 0,
        "unexpected_failures": 0,
        "decisions_created": 0,
        "decisions_refreshed": 0,
    }

    def classify_error(stage: str, error: str) -> str:
        normalized = error.lower()
        if stage == "strategies" and "no eligible option strategies generated" in normalized:
            return "GOVERNED_NO_STRATEGY"
        if stage == "contracts" and "no executable contract recommendation generated" in normalized:
            return "GOVERNED_NO_CONTRACT"
        if stage == "contracts" and "no persisted polygon option data found" in normalized:
            return "MISSING_OPTION_DATA"
        return "UNEXPECTED_FAILURE"

    def execute(name: str, enabled: bool, operation) -> None:
        if not enabled:
            stages[name] = {"status": "SKIPPED", "reason": "DISABLED_BY_REQUEST"}
            print(f"Institutional Options {name}: skipped by request")
            return
        with SessionLocal() as session:
            stage_started = perf_counter()
            try:
                result = operation(session)
                session.commit()
                payload = dict(result.__dict__)
                payload["duration_seconds"] = round(perf_counter() - stage_started, 4)
                raw_errors = tuple(payload.get("errors") or ())
                classified = [
                    {"classification": classify_error(name, error), "detail": error}
                    for error in raw_errors
                ]
                counts = {
                    "governed_no_strategy": sum(
                        item["classification"] == "GOVERNED_NO_STRATEGY" for item in classified
                    ),
                    "governed_no_contract": sum(
                        item["classification"] == "GOVERNED_NO_CONTRACT" for item in classified
                    ),
                    "missing_option_data": sum(
                        item["classification"] == "MISSING_OPTION_DATA" for item in classified
                    ),
                    "unexpected_failures": sum(
                        item["classification"] == "UNEXPECTED_FAILURE" for item in classified
                    ),
                }
                payload.update(counts)
                payload["classified_outcomes"] = classified
                payload["status"] = (
                    "FAILED" if counts["unexpected_failures"]
                    else "DEGRADED" if raw_errors
                    else "READY"
                )
                stages[name] = payload

                if name == "strategies":
                    summary["strategies_generated"] = int(payload.get("generated") or 0)
                elif name == "contracts":
                    summary["contracts_optimized"] = int(payload.get("optimized") or 0)
                elif name == "decisions":
                    summary["decisions_created"] = int(payload.get("created") or 0)
                    summary["decisions_refreshed"] = int(payload.get("refreshed") or 0)
                for key in (
                    "governed_no_strategy", "governed_no_contract",
                    "missing_option_data", "unexpected_failures",
                ):
                    summary[key] += counts[key]

                display_keys = (
                    "requested", "generated", "optimized", "created", "refreshed",
                    "failed", "eligible_candidates", "rejected_candidates",
                    "executable_recommendations", "non_executable_recommendations",
                    "governed_no_strategy", "governed_no_contract",
                    "missing_option_data", "unexpected_failures",
                )
                display = ", ".join(
                    f"{key}={payload[key]}" for key in display_keys if key in payload
                )
                print(
                    f"Institutional Options {name}: status={payload['status']}; {display}; "
                    f"duration={payload.get('duration_seconds', 0)}s"
                )
                for item in classified[:20]:
                    print(
                        f"Institutional Options {name} outcome "
                        f"[{item['classification']}]: {item['detail']}"
                    )

                if counts["unexpected_failures"]:
                    unexpected_failures.extend(
                        f"{name}: {item['detail']}" for item in classified
                        if item["classification"] == "UNEXPECTED_FAILURE"
                    )
                if require_complete:
                    completeness_failures.extend(
                        f"{name}: {item['classification']}: {item['detail']}"
                        for item in classified
                    )

                requested = int(payload.get("requested") or 0)
                useful = int(
                    payload.get("generated") or payload.get("optimized")
                    or payload.get("created") or payload.get("refreshed") or 0
                )
                governed = sum(counts.values()) - counts["unexpected_failures"]
                if requested > 0 and useful == 0 and governed == 0 and not raw_errors:
                    detail = f"{name}: stage produced no usable output"
                    unexpected_failures.append(detail)
                    summary["unexpected_failures"] += 1
                    payload["status"] = "FAILED"
            except Exception as exc:
                session.rollback()
                detail = f"{type(exc).__name__}: {exc}"
                stages[name] = {
                    "status": "FAILED",
                    "error": detail,
                    "unexpected_failures": 1,
                }
                unexpected_failures.append(f"{name}: {detail}")
                summary["unexpected_failures"] += 1
                print(f"Institutional Options {name} failed: {detail}")

    if stock_scanner_run_id is not None and not scoped_opportunity_ids:
        for name, enabled in (("strategies", run_strategies), ("contracts", run_contracts), ("decisions", run_decisions)):
            if enabled:
                stages[name] = {"status": "SKIPPED", "reason": "NO_OPPORTUNITIES_IN_LATEST_PUBLICATION"}
                print(f"Institutional Options {name}: skipped; no opportunities belong to the latest Stock Intelligence run")
        run_strategies = run_contracts = run_decisions = False

    execute(
        "strategies",
        run_strategies,
        lambda session: InstitutionalStrategyGenerationService(session).generate(opportunity_ids=scoped_opportunity_ids, limit=limit),
    )
    execute(
        "contracts",
        run_contracts,
        lambda session: InstitutionalContractOptimizationService(session).optimize(opportunity_ids=scoped_opportunity_ids, limit=limit),
    )
    # Milestone 69 valuation is deliberately positioned after exact-contract
    # optimization and before Institutional Decision Snapshot construction.
    # This ensures decisions consume current fair value, mispricing, relative-
    # value, event, dealer-flow, surface, and executable-edge evidence natively.
    if run_option_valuation:
        valuation = refresh_option_valuation_intelligence(
            required=require_option_valuation,
            limit=option_valuation_limit,
            opportunity_ids=scoped_opportunity_ids,
            scope="CURRENT_RUN",
        )
        stages["option_valuation"] = valuation
        if valuation.get("status") == "FAILED":
            summary["unexpected_failures"] += 1
            unexpected_failures.append(
                "option_valuation: " + str(valuation.get("error") or "valuation refresh failed")
            )
    else:
        stages["option_valuation"] = {
            "status": "SKIPPED",
            "reason": "DISABLED_BY_REQUEST",
        }
        print("Option Valuation Intelligence: skipped by request")

    execute(
        "decisions",
        run_decisions,
        lambda session: InstitutionalDecisionService(session).build(opportunity_ids=scoped_opportunity_ids, limit=limit),
    )

    if stock_scanner_run_id is None:
        detail = "No usable current_stock_intelligence publication is available for Institutional Options advancement"
        payload = {
            "status": "FAILED" if require_success else "DEGRADED",
            "stages": stages,
            "summary": summary,
            "unexpected_failures": [detail],
            "completeness_failures": [detail],
        }
        if require_success:
            raise RuntimeError(detail)
        return payload

    governed_or_coverage = (
        summary["governed_no_strategy"]
        + summary["governed_no_contract"]
        + summary["missing_option_data"]
    )
    status = (
        "FAILED" if unexpected_failures
        else "DEGRADED" if governed_or_coverage
        else "READY"
    )
    payload: dict[str, object] = {
        "status": status,
        "stages": stages,
        "summary": summary,
        "unexpected_failures": unexpected_failures,
        "completeness_failures": completeness_failures,
    }
    print(
        "Institutional Options advancement summary: "
        + ", ".join(f"{key}={value}" for key, value in summary.items())
    )
    if require_success and unexpected_failures:
        raise RuntimeError(
            "Institutional Options downstream advancement encountered unexpected failures: "
            + "; ".join(unexpected_failures)
        )
    if require_complete and completeness_failures:
        raise RuntimeError(
            "Institutional Options downstream advancement did not achieve complete coverage: "
            + "; ".join(completeness_failures)
        )
    return payload


def date_from_args(args: argparse.Namespace) -> date:
    return date.fromisoformat((args.end or date.today().isoformat())[:10])
