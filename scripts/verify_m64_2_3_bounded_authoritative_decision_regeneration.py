#!/usr/bin/env python
from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def check(label: str, condition: bool) -> bool:
    print(f"{'PASS' if condition else 'FAIL'} {label}")
    return bool(condition)


def main() -> None:
    decision = (ROOT / "src/trading_ai/portfolio_risk_allocation/decision_intelligence.py").read_text()
    optimizer = (ROOT / "src/trading_ai/portfolio_risk_allocation/optimizer.py").read_text()
    orchestration = (ROOT / "src/trading_ai/portfolio_risk_allocation/orchestration.py").read_text()
    risk_service = (ROOT / "src/trading_ai/portfolio_risk_allocation/service.py").read_text()
    risk_audit = (ROOT / "scripts/run_m64_2_risk_expiration_audit.py").read_text()
    governance_audit = (ROOT / "scripts/run_m76_2_4_portfolio_governance_audit.py").read_text()
    handoff = (ROOT / "src/trading_ai/institutional_options/handoff.py").read_text()
    router = (ROOT / "src/trading_ai/institutional_options/router.py").read_text()
    regeneration = (ROOT / "scripts/run_m64_2_1_regenerate_current_portfolio_decisions.py").read_text()

    checks = [
        check("pinned_risk_assessment", "risk_snapshot_id: str | None = None" in risk_service and "self.snapshot(portfolio_id, risk_snapshot_id)" in risk_service),
        check("current_stock_run_scope", "InstitutionalOpportunityModel.stock_scanner_run_id == current_stock_run_id" in decision),
        check("complete_source_coverage", "DecisionGenerationCoverageError" in decision and "missing_source_ids" in decision),
        check("staged_before_publication", 'generation_status = "CURRENT" if already_authoritative else "STAGED"' in decision),
        check("atomic_activation", "activate_generation" in decision and "_retire_stale_decisions" in decision),
        check("publication_authority_reader", "_authoritative_risk_snapshot_id" in decision and "current_portfolio_allocation" in decision),
        check("serialized_full_cycle", "pg_try_advisory_lock" in orchestration and "risk_snapshot_id=risk['snapshot_id']" in orchestration),
        check("serialized_publication", "m64_authoritative_publish" in optimizer and "Refused to replace a newer" in optimizer),
        check("optimizer_exact_coverage", "eligible_ids - decision_ids" in optimizer and "activate_generation" in optimizer),
        check("audit_governed_projection", "authoritative_risk_snapshot_id" in risk_audit and "capital.get('open_risk'" in risk_audit),
        check("governance_authority_projection", "publication_matches_current_stock_run" in governance_audit),
        check("handoff_fail_closed", "Portfolio decision is not authoritative" in handoff),
        check("workspace_current_only", "_authoritative_portfolio_decision" in router),
        check("bounded_stale_retirement", "STALE_RETIREMENT_BATCH_SIZE = 500" in decision and "POSTGRESQL_SERVER_SIDE_JSONB" in decision),
        check("historical_orm_materialization_removed", "select(PortfolioDecisionIntelligenceModel).where(\n                PortfolioDecisionIntelligenceModel.portfolio_id == portfolio_id,\n                PortfolioDecisionIntelligenceModel.risk_snapshot_id != current_risk_snapshot_id" not in decision),
        check("retirement_batch_telemetry", "stale_decision_retirement_batch" in decision),
        check("stage_level_telemetry", "decision_generation_started" in orchestration and "optimizer_publication_started" in orchestration),
        check("reusable_governed_risk", "LATEST_READY_REUSE" in orchestration and "GOVERNED_PRE_EXPIRATION_DEFINED_LOSS" in orchestration),
        check("operator_recovery_default", "--rebuild-risk" in regeneration and "last_completed_stage" in regeneration),
    ]
    if not all(checks):
        raise SystemExit("M64.2.3 bounded authoritative decision regeneration verification FAILED")
    print("M64.2.3 bounded authoritative decision regeneration verification PASSED")


if __name__ == "__main__":
    main()
