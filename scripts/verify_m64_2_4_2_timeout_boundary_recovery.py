#!/usr/bin/env python
"""Static release-contract verification for M64.2.4.2."""
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
    wrapper = read(
        "scripts/run_m64_2_4_2_regenerate_authoritative_portfolio_decisions.py"
    )

    checks = {
        "query_cancel_sqlstate_recognized": all(
            token in decisions
            for token in (
                "from sqlalchemy.exc import DBAPIError",
                'QUERY_CANCELED_SQLSTATE = "57014"',
                'getattr(exc.orig, "pgcode", None)',
            )
        ),
        "canceled_batch_rolled_back": (
            "except DBAPIError as exc:" in decisions
            and "session.rollback()" in decisions
        ),
        "canceled_batch_is_retryable": all(
            token in decisions
            for token in (
                'deferred_reason = "POSTGRESQL_QUERY_CANCELED"',
                "historical_decision_cleanup_batch_deferred",
                '"status": "COMPLETE" if complete else "INCOMPLETE_RETRYABLE"',
            )
        ),
        "practical_timeout_floor": all(
            token in decisions
            for token in (
                "HISTORY_CLEANUP_MIN_BATCH_BUDGET_SECONDS = 20.0",
                "HISTORY_CLEANUP_FINALIZATION_RESERVE_SECONDS = 10.0",
                "HISTORY_CLEANUP_MIN_STATEMENT_TIMEOUT_MS = 10_000",
            )
        ),
        "committed_progress_preserved": all(
            token in decisions
            for token in (
                "historical_decision_cleanup_batch_committed",
                "session.commit()",
                "<> 'SUPERSEDED'",
            )
        ),
        "operator_exit_75": (
            "M64HistoryCleanupIncompleteError" in operator
            and "return 75" in operator
            and "M64.2.4.3-REGENERATION-PROGRESS-1.0" in operator
            and "m64-2-4-3-governed-purge-recovery" in operator
        ),
        "operator_wrapper": (
            "run_m64_2_1_regenerate_current_portfolio_decisions" in wrapper
        ),
        "structured_retry_contract": all(
            token in orchestration
            for token in (
                "M64HistoryCleanupIncompleteError",
                "DEFERRED_HISTORY_CLEANUP",
                '"retryable": True',
            )
        ),
    }
    result = {
        "version": "M64.2.4.2-STATIC-RELEASE-VERIFICATION-1.0",
        "status": "PASSED" if all(checks.values()) else "FAILED",
        "checks": checks,
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["status"] == "PASSED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
