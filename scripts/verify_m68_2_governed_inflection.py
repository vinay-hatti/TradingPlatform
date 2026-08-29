from __future__ import annotations

import argparse
import ast
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def static_checks() -> dict[str, bool]:
    engine = (ROOT / "src/trading_ai/inflection_intelligence/engine.py").read_text()
    service = (ROOT / "src/trading_ai/inflection_intelligence/service.py").read_text()
    models = (ROOT / "src/trading_ai/inflection_intelligence/models.py").read_text()
    ingestion = (ROOT / "scripts/ingestion_split_common.py").read_text()
    analytics = (ROOT / "src/trading_ai/analytics_dashboard/service.py").read_text()
    valuation = (ROOT / "src/trading_ai/option_valuation_intelligence/service.py").read_text()
    position = (ROOT / "src/trading_ai/autonomous_position_management/service.py").read_text()
    ui = (ROOT / "ui/workstation/src/InflectionAnalyticsPage.tsx").read_text()
    mispricing_ui = (
        ROOT / "ui/workstation/src/OptionsMispricingAnalyticsPage.tsx"
    ).read_text()
    certification = (
        ROOT / "src/trading_ai/trade_plan_certification/engine.py"
    ).read_text()
    management = (
        ROOT / "src/trading_ai/institutional_options/management.py"
    ).read_text()
    handoff = (
        ROOT / "src/trading_ai/institutional_options/handoff.py"
    ).read_text()
    opportunity_ingestion = (
        ROOT / "src/trading_ai/institutional_options/opportunity_ingestion.py"
    ).read_text()
    repository = (
        ROOT / "src/trading_ai/institutional_options/repository.py"
    ).read_text()
    contract_optimization = (
        ROOT / "src/trading_ai/institutional_options/contract_optimization.py"
    ).read_text()
    recovery = (
        ROOT / "scripts/run_m68_2_recover_current_authority.py"
    ).read_text()
    migration = (
        ROOT / "migrations/versions/m68_002_governed_directional_inflection.py"
    ).read_text()
    for path in (
        ROOT / "src/trading_ai/inflection_intelligence/engine.py",
        ROOT / "src/trading_ai/inflection_intelligence/service.py",
        ROOT / "src/trading_ai/inflection_intelligence/models.py",
        ROOT / "src/trading_ai/trade_plan_certification/engine.py",
        ROOT / "src/trading_ai/institutional_options/management.py",
        ROOT / "src/trading_ai/institutional_options/handoff.py",
        ROOT / "src/trading_ai/institutional_options/opportunity_ingestion.py",
        ROOT / "src/trading_ai/institutional_options/repository.py",
        ROOT / "src/trading_ai/institutional_options/contract_optimization.py",
        ROOT / "scripts/run_m68_2_inflection_cleanup.py",
        ROOT / "scripts/run_m68_2_recover_current_authority.py",
        ROOT / "scripts/verify_m68_2_governed_inflection.py",
        ROOT / "migrations/versions/m68_002_governed_directional_inflection.py",
    ):
        ast.parse(path.read_text(), filename=str(path))
    options_branch = ingestion[ingestion.index('scope == "options"'):]
    options_branch = options_branch[:options_branch.index("elif not args.skip_stock_intelligence")]
    return {
        "signed_direction_and_strength_separated": (
            '"directional_score"' in engine and '"signal_strength"' in engine
        ),
        "neutral_deadband": "NEUTRAL_DEADBAND" in engine,
        "missing_options_abstain": (
            'build_mode == "OPTIONS_ENRICHMENT"' in engine
            and 'disposition = "ABSTAIN"' in engine
        ),
        "point_in_time_breadth_resolver": (
            "_breadth_payload" in service
            and "SectorBreadthSnapshotModel.snapshot_timestamp" in service
            and "<= publication_timestamp" in service
            and "CANONICAL_MARKET_FALLBACK" in service
            and 'original_payload.get("context_score")' not in service
        ),
        "source_lineage_date_parser_complete": (
            'def _as_date(value: object) -> date | None:' in service
            and 'return date.fromisoformat(str(value)[:10])' in service
            and service.index('return date.fromisoformat(str(value)[:10])')
                < service.index('def _as_datetime(value: object) -> datetime | None:')
        ),
        "breadth_lineage_json_safe": (
            "def _json_safe(payload: object) -> object:" in service
            and "default=_json_default" in service
            and 'row.snapshot_timestamp.isoformat()' in service
            and 'market.snapshot_timestamp.isoformat()' in service
            and 'overview.snapshot_timestamp.isoformat()' in service
            and "result = _json_safe(result)" in service
        ),
        "breadth_missing_fails_closed": (
            "not breadth_available" in engine
            and "ABSTAIN_INCOMPLETE_BREADTH" in service
        ),
        "fixed_weights_not_renormalized": (
            "FIXED_NO_RENORMALIZATION" in engine
            and "component_decomposition" in engine
            and "/ weight_total" not in engine
        ),
        "real_iv_and_spread_inputs": (
            '"implied_volatility"] = dealer.get("atm_iv")' in service
            and 'governed_inputs["spread_pct"] = spread' in service
        ),
        "real_timeframe_aggregation": (
            'timeframe == "1w"' in service and 'timeframe == "1mo"' in service
        ),
        "atomic_authority_lock": "pg_advisory_xact_lock" in service,
        "authority_noop_fingerprint": (
            "NOOP_UNCHANGED_AUTHORITY" in service
            and "authority_input_fingerprint" in models
        ),
        "semantic_timeline": (
            "semantic_state_hash" in service
            and "event_fingerprint" in models
        ),
        "bounded_history_retention": (
            "SNAPSHOT_RETENTION_RUNS = 40" in service
            and "TIMELINE_RETENTION_EVENTS_PER_SYMBOL = 120" in service
            and "retired_snapshot_rows" in service
        ),
        "options_does_not_republish_stock": (
            "latest_materialized_stock_publication()" in options_branch
            and "_publish_stock_intelligence" not in options_branch
        ),
        "exact_dashboard_lineage": (
            "== publication.source_run_id" in analytics
        ),
        "valuation_fails_closed": (
            "inf_pub.source_run_id == opp.stock_scanner_run_id" in valuation
            and "INFLECTION_INPUTS_INCOMPLETE_OR_DISPOSITION_ABSTAIN" in valuation
        ),
        "autonomous_management_fails_closed": (
            "inf.get('coverage_status')=='CURRENT_EXACT'" in position
            and "inflection=50.0" in position
        ),
        "ui_exposes_governance_and_signed_score": (
            "Authority coverage" in ui and "Signed score" in ui
            and "Input quality" in ui
        ),
        "inflection_candidate_explorer_header_filters_and_inline_rows": (
            "HEADER_FILTER_FIELDS" in ui
            and "CandidateHeaderFilter" in ui
            and "headerFilterStyle" in ui
            and "opportunity_state" in ui
            and "coverage_status" in ui
            and "directionalScoreBand" in ui
            and "minimumOpportunityScore" in ui
            and "expandedSnapshotId" in ui
            and "aria-expanded" in ui
            and "InlineCandidateDetail" in ui
            and "DetailDrawer" not in ui
            and "repeat(auto-fit, minmax(175px, 1fr))" not in ui
        ),
        "inflection_candidate_inline_detail_is_compact": (
            "borderLeft: '2px solid var(--accent)'" in ui
            and "repeat(3, minmax(250px, 1fr))" in ui
            and "columns: evidence.length > 4 ? 2 : 1" in ui
            and "conflicts.length > 0 && <section>" in ui
        ),
        "inflection_candidate_inline_detail_is_readable": (
            "fontSize: 13" in ui
            and "fontSize: 12" in ui
            and "lineHeight: 1.35" in ui
        ),
        "mispricing_candidate_excel_header_filters": (
            "HEADER_FILTER_FIELDS" in mispricing_ui
            and "CandidateHeaderFilter" in mispricing_ui
            and "headerFilterStyle" in mispricing_ui
            and "marketBand" in mispricing_ui
            and "fairValueBand" in mispricing_ui
            and "mispricingBand" in mispricing_ui
            and "minimumEdge" in mispricing_ui
            and "minimumProbability" in mispricing_ui
            and "expectedValueBand" in mispricing_ui
            and "minimumReturn" in mispricing_ui
            and "minimumLiquidity" in mispricing_ui
            and "minimumStability" in mispricing_ui
        ),
        "mispricing_candidate_inline_detail_complete": (
            "expandedSnapshotId" in mispricing_ui
            and "aria-expanded" in mispricing_ui
            and "event.key === 'Enter' || event.key === ' '" in mispricing_ui
            and "InlineValuationDetail" in mispricing_ui
            and "Exact market lineage" in mispricing_ui
            and "Relative value" in mispricing_ui
            and "Event pricing" in mispricing_ui
            and "Option legs" in mispricing_ui
            and "DetailDrawer" not in mispricing_ui
            and "AnalyticsTable" not in mispricing_ui
        ),
        "mispricing_candidate_inline_detail_is_readable_compact": (
            "borderLeft: '2px solid var(--accent)'" in mispricing_ui
            and "repeat(3, minmax(270px, 1fr))" in mispricing_ui
            and "fontSize: 13" in mispricing_ui
            and "fontSize: 12" in mispricing_ui
            and "lineHeight: 1.35" in mispricing_ui
        ),
        "conditional_entry_governance": (
            "_entry_execution_readiness" in certification
            and "TARGET_1_REMAINING_ROOM_INSUFFICIENT" in certification
            and "WAITING_FOR_ENTRY" in certification
            and "REGENERATE_REQUIRED" in certification
        ),
        "management_readiness_uses_execution_disposition": (
            'certification.get("trade_builder_ready") is True' in management
            and "m68.2.1-conditional-entry-governance" in management
        ),
        "handoff_requires_ready_now": (
            'execution_certification.get("execution_disposition") != "READY_NOW"'
            in handoff
        ),
        "source_and_contract_option_lineage_separated": (
            "_separate_source_and_contract_option_lineage"
            in opportunity_ingestion
            and "SOURCE_AND_CONTRACT_IDENTITIES_SEPARATED"
            in opportunity_ingestion
            and "m68_2_1_3_source_option_snapshot_id"
            in opportunity_ingestion
            and "contract_snapshot_id" in opportunity_ingestion
        ),
        "missing_exact_contract_is_governed_regeneration": (
            "ContractLineageRegenerationRequired" in management
            and "reset_for_contract_regeneration" in management
            and "contract_regeneration_opportunity_ids" in management
            and "TPC-LIN-021" in repository
            and "TPC-LIN-022" in repository
            and "NO_EXECUTABLE_CURRENT_CONTRACT" in repository
            and "STRATEGIES_GENERATED" in repository
        ),
        "recovery_regenerates_and_recertifies_contracts": (
            "InstitutionalContractOptimizationService" in recovery
            and "post_regeneration_entry_governance" in recovery
            and "falsely_ready_contract_lineage" in recovery
            and "pending_contract_regeneration" in recovery
            and "governed_unavailable" in recovery
            and "unexpected_failures" in recovery
        ),
        "optimizer_requires_selected_strategy_contract": (
            "StrategyComparisonModel" in contract_optimization
            and "selected_executable_count" in contract_optimization
            and "alternative_executable_count" in contract_optimization
            and "for authoritative selected strategy"
                in contract_optimization
            and "m68_2_1_4_selected_strategy_contract_exact"
                in contract_optimization
        ),
        "recovery_resumes_pending_contract_regeneration": (
            "resumed_pending_contract_regeneration_ids" in recovery
            and "m68_2_1_3_contract_regeneration_required" in recovery
            and "STRATEGIES_GENERATED" in recovery
        ),
        "migration_chain": (
            'revision = "m68_002"' in migration
            and 'down_revision = "m71_004"' in migration
        ),
        "bounded_cleanup_confirmation": (
            "PURGE_M68_UNMATERIALIZED_AND_DUPLICATE_TIMELINE"
            in (ROOT / "scripts/run_m68_2_inflection_cleanup.py").read_text()
        ),
    }


def runtime_checks(*, exercise_noop: bool) -> tuple[dict[str, bool], dict]:
    from sqlalchemy import text
    from trading_ai.database.session import SessionLocal
    from trading_ai.inflection_intelligence.service import InstitutionalInflectionService
    from trading_ai.institutional_options.publication_scope import (
        latest_stock_intelligence_publication,
    )

    details: dict = {}
    with SessionLocal() as session:
        target = latest_stock_intelligence_publication(
            session, "current_stock_intelligence", require_materialized=True
        )
        if target is None:
            return {"materialized_stock_authority_exists": False}, details
        target_run = str(target.scanner_run_id)
        row = session.execute(text("""
            SELECT p.source_run_id, p.status, p.symbol_count,
                   p.coverage_status, p.authority_input_fingerprint,
                   p.source_as_of_date, p.option_snapshot_id,
                   COUNT(s.snapshot_id) AS snapshot_count,
                   COUNT(DISTINCT s.symbol) AS distinct_symbols,
                   COUNT(*) FILTER (
                       WHERE s.direction = 'BULLISH'
                         AND s.directional_score < 15
                   ) AS invalid_bullish,
                   COUNT(*) FILTER (
                       WHERE s.direction = 'BEARISH'
                         AND s.directional_score > -15
                   ) AS invalid_bearish,
                   COUNT(*) FILTER (
                       WHERE s.direction = 'NEUTRAL'
                         AND ABS(s.directional_score) >= 15
                   ) AS invalid_neutral,
                   COUNT(*) FILTER (
                       WHERE s.coverage_status = 'CURRENT_EXACT'
                         AND s.payload_json::jsonb #>>
                           '{diagnostics,implied_volatility}' IS NOT NULL
                   ) AS current_real_iv_rows,
                   COUNT(*) FILTER (
                       WHERE s.coverage_status <> 'CURRENT_EXACT'
                   ) AS governed_incomplete_rows,
                   COUNT(*) FILTER (
                       WHERE s.coverage_status = 'CURRENT_EXACT'
                         AND s.payload_json::jsonb #>>
                           '{lineage,component_freshness,breadth}' = 'CURRENT_EXACT'
                         AND s.payload_json::jsonb #>>
                           '{lineage,breadth,as_of_date}' = p.source_as_of_date
                   ) AS exact_breadth_rows,
                   COUNT(*) FILTER (
                       WHERE s.coverage_status = 'CURRENT_EXACT'
                         AND jsonb_typeof(
                           s.payload_json::jsonb #>
                             '{lineage,breadth,snapshot_timestamp}'
                         ) = 'string'
                   ) AS json_safe_breadth_timestamp_rows,
                   COUNT(*) FILTER (
                       WHERE s.payload_json::jsonb #>>
                           '{weight_contract,policy}' = 'FIXED_NO_RENORMALIZATION'
                   ) AS fixed_weight_rows,
                   COUNT(*) FILTER (
                       WHERE (s.payload_json::jsonb #>>
                           '{lineage,breadth,snapshot_timestamp}')::timestamptz
                           > sp.snapshot_timestamp::timestamptz
                   ) AS future_breadth_rows
              FROM institutional_inflection_publications p
              JOIN stock_scanner_publications sp
                ON sp.scanner_run_id = p.source_run_id
               AND sp.publication_name = 'current_stock_intelligence'
              LEFT JOIN institutional_inflection_snapshots s
                ON s.publication_name = p.publication_name
               AND s.source_run_id = p.source_run_id
             WHERE p.publication_name = 'current_institutional_inflection'
             GROUP BY p.source_run_id, p.status, p.symbol_count,
                      p.coverage_status, p.authority_input_fingerprint,
                      p.source_as_of_date, p.option_snapshot_id,
                      sp.snapshot_timestamp
        """)).mappings().one_or_none()
        if row is None:
            return {"inflection_publication_exists": False}, details
        candidate_count = session.execute(text("""
            SELECT COUNT(*) FROM stock_scanner_candidates
             WHERE scanner_run_id = :run_id
        """), {"run_id": target_run}).scalar_one()
        duplicate_events = session.execute(text("""
            SELECT COUNT(*) FROM (
                SELECT event_fingerprint
                  FROM institutional_inflection_timeline_events
                 GROUP BY event_fingerprint
                HAVING COUNT(*) > 1
            ) d
        """)).scalar_one()
        exact_embedded = session.execute(text("""
            SELECT COUNT(*)
              FROM institutional_option_opportunities o
             WHERE o.stock_scanner_run_id = :run_id
               AND o.payload_json::jsonb #>>
                   '{inflection_intelligence,lineage,stock_scanner_run_id}'
                   = :run_id
        """), {"run_id": target_run}).scalar_one()
        opportunity_count = session.execute(text("""
            SELECT COUNT(*) FROM institutional_option_opportunities
             WHERE stock_scanner_run_id = :run_id
        """), {"run_id": target_run}).scalar_one()
        readiness = session.execute(text("""
            SELECT
                COUNT(*) FILTER (
                    WHERE o.state = 'READY_FOR_EXECUTION'
                      AND (
                        e.ready_for_trade_builder IS NOT TRUE
                        OR e.payload_json::jsonb #>>
                          '{trade_plan_certification,execution_disposition}'
                          <> 'READY_NOW'
                      )
                ) AS invalid_ready_rows,
                COUNT(*) FILTER (
                    WHERE o.state <> 'READY_FOR_EXECUTION'
                      AND e.ready_for_trade_builder IS TRUE
                ) AS invalid_nonready_rows
                ,COUNT(*) FILTER (
                    WHERE o.state = 'READY_FOR_EXECUTION'
                      AND NOT EXISTS (
                          SELECT 1
                            FROM institutional_option_strategy_comparisons sc
                            JOIN institutional_option_contract_recommendations c
                              ON c.opportunity_id = o.opportunity_id
                             AND c.strategy_candidate_id =
                                 sc.selected_strategy_candidate_id
                             AND c.option_snapshot_id = o.option_snapshot_id
                             AND c.executable IS TRUE
                           WHERE sc.opportunity_id = o.opportunity_id
                      )
                ) AS falsely_ready_contract_lineage
                ,COUNT(*) FILTER (
                    WHERE o.state = 'READY_FOR_EXECUTION'
                      AND o.option_snapshot_id LIKE 'options-%'
                ) AS ready_rows_using_raw_ingestion_run
                ,COUNT(*) FILTER (
                    WHERE o.state = 'STRATEGIES_GENERATED'
                      AND COALESCE(
                          (o.payload_json::jsonb #>>
                            '{metadata,m68_2_1_3_contract_regeneration_required}')::boolean,
                          false
                      )
                ) AS pending_contract_regeneration
              FROM institutional_option_opportunities o
              LEFT JOIN institutional_option_execution_recommendations e
                ON e.opportunity_id = o.opportunity_id
             WHERE o.stock_scanner_run_id = :run_id
        """), {"run_id": target_run}).mappings().one()
        newer_orphan_publications = session.execute(text("""
            SELECT COUNT(*)
              FROM stock_scanner_publications p
             WHERE p.publication_name = 'current_stock_intelligence'
               AND p.snapshot_timestamp > :target_timestamp
               AND NOT EXISTS (
                    SELECT 1 FROM institutional_option_opportunities o
                     WHERE o.stock_scanner_run_id = p.scanner_run_id
               )
        """), {"target_timestamp": target.snapshot_timestamp}).scalar_one()
        details = {
            **dict(row),
            "target_materialized_stock_run": target_run,
            "stock_candidate_count": int(candidate_count),
            "opportunity_count": int(opportunity_count),
            "exact_embedded_opportunities": int(exact_embedded),
            "duplicate_event_fingerprints": int(duplicate_events),
            "newer_orphan_stock_publications": int(newer_orphan_publications),
            **dict(readiness),
        }
        checks = {
            "materialized_stock_authority_exists": True,
            "authority_run_aligned": row["source_run_id"] == target_run,
            "exact_snapshot_coverage": (
                int(row["snapshot_count"]) == int(candidate_count)
                and int(row["distinct_symbols"]) == int(candidate_count)
                and int(row["symbol_count"]) == int(candidate_count)
            ),
            "coverage_governed": row["coverage_status"] in {
                "COMPLETE", "COMPLETE_WITH_ABSTENTIONS"
            },
            "authority_fingerprint_present": bool(
                row["authority_input_fingerprint"]
            ),
            "source_and_option_lineage_present": bool(
                row["source_as_of_date"] and row["option_snapshot_id"]
            ),
            "directional_semantics_valid": (
                int(row["invalid_bullish"]) == 0
                and int(row["invalid_bearish"]) == 0
                and int(row["invalid_neutral"]) == 0
            ),
            "real_iv_or_governed_abstention": (
                int(row["current_real_iv_rows"])
                + int(row["governed_incomplete_rows"])
                == int(row["snapshot_count"])
            ),
            "point_in_time_breadth_or_governed_abstention": (
                int(row["exact_breadth_rows"])
                + int(row["governed_incomplete_rows"])
                == int(row["snapshot_count"])
            ),
            "no_future_breadth_leakage": int(row["future_breadth_rows"]) == 0,
            "breadth_timestamp_json_materialized": (
                int(row["json_safe_breadth_timestamp_rows"])
                == int(row["exact_breadth_rows"])
            ),
            "fixed_weight_decomposition_materialized": (
                int(row["fixed_weight_rows"]) == int(row["snapshot_count"])
            ),
            "entry_readiness_state_consistent": (
                int(readiness["invalid_ready_rows"] or 0) == 0
                and int(readiness["invalid_nonready_rows"] or 0) == 0
            ),
            "ready_rows_have_exact_selected_contract_lineage": (
                int(readiness["falsely_ready_contract_lineage"] or 0) == 0
                and int(readiness["ready_rows_using_raw_ingestion_run"] or 0)
                    == 0
            ),
            "contract_regeneration_complete": (
                int(readiness["pending_contract_regeneration"] or 0) == 0
            ),
            "timeline_event_fingerprints_unique": int(duplicate_events) == 0,
            "exact_opportunity_embedding": (
                int(exact_embedded) == int(opportunity_count)
            ),
            "no_newer_orphan_stock_publication": (
                int(newer_orphan_publications) == 0
            ),
        }
    if exercise_noop:
        result = InstitutionalInflectionService(SessionLocal).build(
            build_mode="OPTIONS_ENRICHMENT"
        )
        details["noop_probe"] = result
        checks["unchanged_authority_noop"] = (
            result.get("cycle_outcome") == "NOOP_UNCHANGED_AUTHORITY"
            and result.get("authoritative_rebuild_performed") is False
        )
    return checks, details


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--static-only", action="store_true")
    parser.add_argument("--exercise-noop", action="store_true")
    args = parser.parse_args()
    checks = static_checks()
    details = {}
    if not args.static_only:
        runtime, details = runtime_checks(exercise_noop=args.exercise_noop)
        checks.update(runtime)
    payload = {
        "version": (
            "M68.2.1.7-READABLE-INLINE-ANALYTICS-VERIFICATION-1.0"
        ),
        "status": "PASSED" if all(checks.values()) else "FAILED",
        "checks": checks,
        "details": details,
    }
    print(json.dumps(payload, indent=2, sort_keys=True, default=str))
    return 0 if payload["status"] == "PASSED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
