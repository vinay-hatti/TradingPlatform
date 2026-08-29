#!/usr/bin/env python
"""Static release-contract verification for M64.2.4."""
from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read(relative: str) -> str:
    return (ROOT / relative).read_text()


def main() -> int:
    orchestration = read("src/trading_ai/portfolio_risk_allocation/orchestration.py")
    decisions = read("src/trading_ai/portfolio_risk_allocation/decision_intelligence.py")
    optimizer = read("src/trading_ai/portfolio_risk_allocation/optimizer.py")
    broker_sync = read("src/trading_ai/broker_portfolio_sync/service.py")
    scheduler = read("scripts/run_m64_portfolio_intelligence.py")
    operator = read("scripts/run_m64_2_1_regenerate_current_portfolio_decisions.py")
    router = read("src/trading_ai/portfolio_risk_allocation/router.py")
    governance_audit = read("scripts/run_m76_2_4_portfolio_governance_audit.py")
    risk_audit = read("scripts/run_m64_2_risk_expiration_audit.py")

    checks = {
        "bounded_cycle_lock": (
            "pg_try_advisory_lock" in orchestration
            and "M64CycleBusyError" in orchestration
            and "cycle_lock_waiting" in orchestration
            and "lock_timeout_seconds" in orchestration
        ),
        "nonblocking_internal_locks": (
            "pg_try_advisory_xact_lock" in decisions
            and "pg_try_advisory_xact_lock" in optimizer
        ),
        "server_side_retirement": all(token in decisions for token in (
            "WITH candidates AS",
            "FOR UPDATE",
            "jsonb_build_object",
            "sha256(convert_to",
            "POSTGRESQL_SERVER_SIDE_JSONB",
        )),
        "retirement_time_bounds": all(token in decisions for token in (
            "STALE_RETIREMENT_BATCH_SIZE = 500",
            "STALE_RETIREMENT_STATEMENT_TIMEOUT_MS",
            "STALE_RETIREMENT_TOTAL_TIMEOUT_SECONDS",
        )),
        "atomic_publication": (
            "activate_generation" in optimizer
            and "authoritative_publication_commit_started" in optimizer
            and "session.commit()" in optimizer
        ),
        "exact_coverage_gate": all(token in optimizer for token in (
            "eligible_ids",
            "missing_decisions",
            "Portfolio optimizer refused incomplete decision authority",
        )),
        "broker_sync_decoupled": (
            "DEFERRED_TO_DEDICATED_SCHEDULER" in broker_sync
            and "Milestone64ContinuousPortfolioIntelligenceService" not in broker_sync
        ),
        "dedicated_scheduler_telemetry": all(token in scheduler for token in (
            "SCHEDULED-PROGRESS-1.0",
            "cycle_deferred_busy",
            "lock_timeout_seconds=lock_timeout_seconds",
        )),
        "operator_busy_exit": (
            "REGENERATION-PROGRESS-1.0" in operator
            and "return 75" in operator
        ),
        "api_busy_deferred": (
            "API-DEFERRED-1.0" in router
            and "M64CycleBusyError" in router
        ),
        "audit_versions": (
            "M64.2.4-SET-BASED" in governance_audit
            and "M64.2.4-RISK-EXPIRATION" in risk_audit
        ),
    }
    result = {
        "version": "M64.2.4-STATIC-RELEASE-VERIFICATION-1.0",
        "status": "PASSED" if all(checks.values()) else "FAILED",
        "checks": checks,
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["status"] == "PASSED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
