#!/usr/bin/env python
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path


VERSION = "M68.2.1.15.3-POSITIVE-ENTRY-EVIDENCE-VERIFICATION-1.0"
EXACT_CERTIFICATION_ENGINE_SHA256 = (
    "d892f890bd8b7ceaeaf0189709fbb2155e5c60a73d0b7005b0e574fed685e690"
)


def source_checks(root: Path) -> dict[str, bool]:
    authority = (
        root / "src/trading_ai/institutional_options/trade_builder_authority.py"
    ).read_text(encoding="utf-8")
    decision = (
        root / "src/trading_ai/institutional_options/decision.py"
    ).read_text(encoding="utf-8")
    repository = (
        root / "src/trading_ai/institutional_options/repository.py"
    ).read_text(encoding="utf-8")
    advancement = (
        root / "src/trading_ai/institutional_options/advancement_authority.py"
    ).read_text(encoding="utf-8")
    certification_path = (
        root / "src/trading_ai/trade_plan_certification/engine.py"
    )
    certification_bytes = certification_path.read_bytes()
    certification = certification_bytes.decode("utf-8")
    optimizer = (
        root / "src/trading_ai/portfolio_risk_allocation/optimizer.py"
    ).read_text(encoding="utf-8")
    contract_optimizer = (
        root / "src/trading_ai/institutional_options/contract_optimization.py"
    ).read_text(encoding="utf-8")
    breadth_governance_test = (
        root
        / "tests/milestone68/test_m68_2_1_breadth_entry_governance.py"
    ).read_text(encoding="utf-8")
    decision_intelligence = (
        root / "src/trading_ai/portfolio_risk_allocation/decision_intelligence.py"
    ).read_text(encoding="utf-8")
    migration = (
        root / "migrations/versions/m68_004_certified_trade_builder_authority.py"
    ).read_text(encoding="utf-8")
    recovery = (
        root / "scripts/run_m68_2_1_15_rebuild_certified_global_authority.py"
    ).read_text(encoding="utf-8")
    return {
        "canonical_certification_authority": (
            "FINAL_CERTIFICATION_SCOPE" in authority
            and "READY_EXECUTION_DISPOSITION" in authority
            and '"authorized": bool(certification_valid and column_ready)'
                in authority
            and "blocking_reason_codes" in authority
            and "entry_reason_codes" in authority
            and "certification_valid = not blocking_reasons" in authority
        ),
        "ready_lifecycle_requires_certification": (
            "classify_trade_builder_authority" in decision
            and 'authority["authorized"] is True' in decision
            and '"WAITING_FOR_ENTRY"' in decision
            and '"REGENERATE_REQUIRED"' in decision
        ),
        "repository_derives_ready_flag": (
            "column_consistent" in repository
            and 'ready_for_trade_builder=authority["authorized"]' in repository
        ),
        "advancement_blocks_invalid_readiness": (
            "readiness_integrity_report" in advancement
            and "INVALID_TRADE_BUILDER_READINESS" in advancement
        ),
        "conditional_entry_interface_restored": (
            "entry_policy: dict | None = None" in certification
            and "geometry_context: dict | None = None" in certification
            and "TARGET_1_REMAINING_ROOM_INSUFFICIENT" in certification
            and "WAITING_FOR_ENTRY" in certification
            and "READY_NOW" in certification
        ),
        "exact_current_certification_engine_preserved": (
            hashlib.sha256(certification_bytes).hexdigest()
            == EXACT_CERTIFICATION_ENGINE_SHA256
            and "_entry_execution_readiness" in certification
            and "TPC-EXEC-004" in certification
        ),
        "portfolio_eligibility_is_certified": (
            "certified_ready_opportunity_ids" in optimizer
            and "certified_ready_opportunity_ids" in decision_intelligence
        ),
        "legacy_selected_only_contract_test_superseded": (
            "EXHAUSTIVE_EXECUTABLE_PACKAGE_AUTHORITY" in contract_optimizer
            and "all_eligible_strategies_evaluated" in contract_optimizer
            and "higher_ranked_feasible_excluded" in contract_optimizer
            and "selected_executable_count" not in contract_optimizer
            and "globally_selects_feasible_package" in breadth_governance_test
            and 'assert "selected_executable_count" not in optimizer'
                in breadth_governance_test
        ),
        "full_universe_stage_ledger": (
            "terminal_stage_counts" in optimizer
            and "hard_gate_reason_counts" in optimizer
            and "strategy_package_count" in optimizer
            and "contract_package_count" in optimizer
            and "INVALID_READY_INVARIANT" in optimizer
        ),
        "database_blocks_future_false_ready": (
            "NOT VALID" in migration
            and "IS TRUE" in migration
            and "INSTITUTIONAL_OPTIONS_FINAL_PLAN" in migration
            and "READY_NOW" in migration
        ),
        "controlled_rebuild_covers_source_universe": (
            "InstitutionalOpportunityIngestionService" in recovery
            and "latest_published_stock_scanner_run_id" in recovery
            and "reconcile_historical_ready_flags" in recovery
            and ") IS TRUE)" in recovery
            and "VALIDATE CONSTRAINT" in recovery
            and "REBUILD_M68_2_1_15_CERTIFIED_GLOBAL_AUTHORITY" in recovery
        ),
        "recovery_writes_failure_manifest": (
            '"mode": "EXECUTION_FAILED"' in recovery
            and 'progress("recovery_failed"' in recovery
            and 'Path(args.manifest).write_text' in recovery
        ),
    }


def behavior_checks(root: Path) -> dict[str, bool]:
    authority_path = (
        root / "src/trading_ai/institutional_options/trade_builder_authority.py"
    )
    spec = importlib.util.spec_from_file_location(
        "m68_2_1_15_3_trade_builder_authority_probe",
        authority_path,
    )
    if spec is None or spec.loader is None:
        return {
            "positive_ready_now_evidence_authorizes": False,
            "non_ready_disposition_still_blocks": False,
        }
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    classify_trade_builder_authority = (
        module.classify_trade_builder_authority
    )

    passing = {
        "certification_id": "TPC-IO-ENTRY-EVIDENCE-PROBE",
        "status": "PASS",
        "certification_scope": "INSTITUTIONAL_OPTIONS_FINAL_PLAN",
        "execution_disposition": "READY_NOW",
        "trade_builder_ready": True,
        "plan_fingerprint": "entry-evidence-probe",
        "failure_codes": [],
        "entry_execution": {
            "disposition": "READY_NOW",
            "trade_builder_ready": True,
            "reason_codes": [
                "REFERENCE_PRICE_WITHIN_GOVERNED_ENTRY_RANGE"
            ],
        },
    }
    ready = classify_trade_builder_authority(
        {"trade_plan_certification": passing},
        True,
    )
    waiting = dict(passing)
    waiting.update({
        "execution_disposition": "WAITING_FOR_ENTRY",
        "trade_builder_ready": False,
        "entry_execution": {
            "disposition": "WAITING_FOR_ENTRY",
            "trade_builder_ready": False,
            "reason_codes": [
                "ABOVE_CHASE_LIMIT_WAIT_FOR_PULLBACK_OR_CONFIRMATION"
            ],
        },
    })
    blocked = classify_trade_builder_authority(
        {"trade_plan_certification": waiting},
        False,
    )
    return {
        "positive_ready_now_evidence_authorizes": (
            ready["authorized"] is True
            and ready["certification_valid"] is True
            and ready["column_consistent"] is True
            and ready["blocking_reason_codes"] == []
            and ready["entry_reason_codes"] == [
                "REFERENCE_PRICE_WITHIN_GOVERNED_ENTRY_RANGE"
            ]
        ),
        "non_ready_disposition_still_blocks": (
            blocked["authorized"] is False
            and blocked["column_consistent"] is True
            and "EXECUTION_DISPOSITION_NOT_READY_NOW"
                in blocked["blocking_reason_codes"]
            and "ABOVE_CHASE_LIMIT_WAIT_FOR_PULLBACK_OR_CONFIRMATION"
                in blocked["entry_reason_codes"]
        ),
    }


def runtime_checks() -> tuple[dict[str, bool], dict]:
    from sqlalchemy import text

    from trading_ai.database.session import SessionLocal
    from trading_ai.institutional_options.models import (
        InstitutionalDecisionSnapshotModel,
        InstitutionalOpportunityModel,
    )
    from trading_ai.institutional_options.publication_scope import (
        latest_published_stock_scanner_run_id,
        latest_stock_scanner_run_id,
    )
    from trading_ai.institutional_options.trade_builder_authority import (
        certified_ready_opportunity_ids,
        readiness_integrity_report,
    )
    from trading_ai.portfolio_risk_allocation.config import (
        load_portfolio_optimizer_config,
    )
    from trading_ai.portfolio_risk_allocation.models import (
        PortfolioIntelligencePublicationModel,
    )
    from trading_ai.stock_intelligence.models import StockScannerCandidateModel

    config = load_portfolio_optimizer_config()
    with SessionLocal() as session:
        run_id = latest_stock_scanner_run_id(session)
        published_run_id = latest_published_stock_scanner_run_id(session)
        source_count = (
            session.query(StockScannerCandidateModel)
            .filter_by(scanner_run_id=run_id)
            .count()
            if run_id else 0
        )
        integrity = (
            readiness_integrity_report(
                session,
                stock_scanner_run_id=run_id,
            )
            if run_id else {}
        )
        certified_ids = (
            certified_ready_opportunity_ids(
                session,
                stock_scanner_run_id=run_id,
            )
            if run_id else set()
        )
        publication = (
            session.query(PortfolioIntelligencePublicationModel)
            .filter_by(
                portfolio_id="PAPER-PRIMARY",
                publication_name="current_portfolio_allocation",
            )
            .one_or_none()
        )
        publication_payload = (
            {} if publication is None else dict(publication.payload_json or {})
        )
        global_authority = dict(
            publication_payload.get("global_candidate_authority") or {}
        )
        proof = dict(publication_payload.get("optimization_proof") or {})
        current_opportunity_ids = {
            str(value) for (value,) in (
                session.query(InstitutionalOpportunityModel.opportunity_id)
                .filter_by(stock_scanner_run_id=run_id)
                .all()
                if run_id else ()
            )
        }
        decisions = (
            session.query(InstitutionalDecisionSnapshotModel)
            .filter(
                InstitutionalDecisionSnapshotModel.opportunity_id.in_(
                    current_opportunity_ids
                )
            )
            .all()
            if current_opportunity_ids else []
        )
        selected_ids = {
            str(row.opportunity_id) for row in decisions
            if (
                dict(
                    (dict(row.payload_json or {}).get("portfolio_decision") or {})
                    .get("optimizer_selection") or {}
                ).get("selected") is True
            )
        }
        constraint_validated = bool(session.scalar(text("""
            SELECT convalidated
            FROM pg_constraint
            WHERE conname = 'ck_m62_ready_requires_final_certification'
        """)))

    terminal_counts = dict(global_authority.get("terminal_stage_counts") or {})
    terminal_total = sum(int(value or 0) for value in terminal_counts.values())
    checks = {
        "runtime_publication_exists": publication is not None,
        "runtime_source_universe_present": source_count > 0,
        "runtime_latest_published_authority_materialized": (
            run_id is not None and run_id == published_run_id
        ),
        "runtime_no_invalid_readiness": (
            integrity.get("invalid_readiness_count") == 0
        ),
        "runtime_ready_equals_certified": (
            integrity.get("ready_state_count") == len(certified_ids)
            and integrity.get("ready_flag_count") == len(certified_ids)
        ),
        "runtime_all_source_candidates_classified": (
            global_authority.get("all_source_candidates_classified") is True
            and int(global_authority.get("source_universe_count") or 0)
                == source_count
            and terminal_total == source_count
        ),
        "runtime_no_unclassified_bug_stage": (
            int(terminal_counts.get("NOT_MATERIALIZED_BUG") or 0) == 0
            and int(terminal_counts.get("INVALID_READY_INVARIANT") or 0) == 0
        ),
        "runtime_certified_executable_count_matches": (
            int(global_authority.get("executable_now_count") or -1)
                == len(certified_ids)
        ),
        "runtime_optimizer_selected_only_certified": (
            selected_ids.issubset(certified_ids)
        ),
        "runtime_global_claim_and_optimality_proven": (
            global_authority.get("status") == "PROVEN"
            and global_authority.get("optimality_proven") is True
            and proof.get("optimality_proven") is True
        ),
        "runtime_selected_within_env_cap": (
            len(selected_ids) <= config.max_new_positions
        ),
        "runtime_env_cap_is_requested_100": (
            config.max_new_positions == 100
        ),
        "runtime_database_constraint_validated": constraint_validated,
    }
    details = {
        "stock_scanner_run_id": run_id,
        "latest_published_stock_scanner_run_id": published_run_id,
        "publication_id": (
            None if publication is None else publication.publication_id
        ),
        "source_universe_count": source_count,
        "materialized_opportunity_count": global_authority.get(
            "materialized_opportunity_count"
        ),
        "source_eligible_count": global_authority.get("source_eligible_count"),
        "strategy_package_count": global_authority.get("strategy_package_count"),
        "contract_package_count": global_authority.get("contract_package_count"),
        "certified_executable_now_count": len(certified_ids),
        "selected_global_feasible_count": len(selected_ids),
        "max_new_positions": config.max_new_positions,
        "max_new_positions_source": config.source,
        "terminal_stage_counts": terminal_counts,
        "hard_gate_reason_counts": global_authority.get(
            "hard_gate_reason_counts"
        ),
        "readiness_integrity": integrity,
        "constraint_validated": constraint_validated,
    }
    return checks, details


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=str(Path(__file__).resolve().parents[1]))
    parser.add_argument("--runtime", action="store_true")
    args = parser.parse_args()
    root = Path(args.root).resolve()
    checks = source_checks(root)
    checks.update(behavior_checks(root))
    details = {}
    if args.runtime:
        runtime, details = runtime_checks()
        checks.update(runtime)
    passed = all(checks.values())
    print(json.dumps({
        "version": VERSION,
        "status": "PASSED" if passed else "FAILED",
        "checks": checks,
        "details": details,
    }, indent=2, sort_keys=True, default=str))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
