#!/usr/bin/env python
"""Compatibility verification for superseded M64.2.4.1 cleanup behavior."""
from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read(relative: str) -> str:
    return (ROOT / relative).read_text()


def main() -> int:
    decisions = read(
        "src/trading_ai/portfolio_risk_allocation/decision_intelligence.py"
    )
    orchestration = read(
        "src/trading_ai/portfolio_risk_allocation/orchestration.py"
    )
    operator = read(
        "scripts/run_m64_2_1_regenerate_current_portfolio_decisions.py"
    )
    scheduler = read("scripts/run_m64_portfolio_intelligence.py")
    router = read("src/trading_ai/portfolio_risk_allocation/router.py")
    wrapper = read(
        "scripts/run_m64_2_4_1_regenerate_authoritative_portfolio_decisions.py"
    )

    checks = {
        "resumable_committed_cleanup": all(token in decisions for token in (
            "compact_non_authoritative_history",
            "POSTGRESQL_RESUMABLE_COMMITTED_JSONB",
            "historical_decision_cleanup_batch_committed",
            "session.commit()",
        )),
        "authoritative_publication_preserved": all(
            token in decisions
            for token in (
                "current_portfolio_allocation",
                "risk_snapshot_id <> :authoritative_risk_snapshot_id",
                "NON_AUTHORITATIVE_HISTORY_COMPACTION",
            )
        ),
        "cursor_bounded_batches": all(token in decisions for token in (
            "HISTORY_CLEANUP_BATCH_SIZE = 1_000",
            "decision_intelligence_id > CAST(:cursor AS text)",
            "HISTORY_CLEANUP_WORK_BUDGET_SECONDS",
        )),
        "exact_remaining_verification": (
            '"remaining": remaining' in decisions
            and "complete = remaining == 0" in decisions
        ),
        "structured_retry": all(token in orchestration for token in (
            "M64HistoryCleanupIncompleteError",
            "DEFERRED_HISTORY_CLEANUP",
            '"retryable": True',
        )),
        "legacy_cleanup_not_authority_gate": (
            "compact_non_authoritative_history" not in orchestration
            and "historical_governance_ready" in orchestration
        ),
        "operator_exit_75": (
            "M64HistoryCleanupIncompleteError" in operator
            and "return 75" in operator
            and "M64.2.4.3-REGENERATION-PROGRESS-1.0" in operator
        ),
        "scheduler_uses_nonblocking_retention": (
            "M64HistoryCleanupIncompleteError" not in scheduler
            and "prune_expired_history" in orchestration
        ),
        "api_deferred_contract": (
            "M64HistoryCleanupIncompleteError" in router
            and "M64.2.4.3-API-DEFERRED-1.0" in router
        ),
        "operator_wrapper": (
            "run_m64_2_1_regenerate_current_portfolio_decisions" in wrapper
        ),
    }
    result = {
        "version": "M64.2.4.3-LEGACY-CLEANUP-COMPATIBILITY-1.0",
        "status": "PASSED" if all(checks.values()) else "FAILED",
        "checks": checks,
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["status"] == "PASSED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
