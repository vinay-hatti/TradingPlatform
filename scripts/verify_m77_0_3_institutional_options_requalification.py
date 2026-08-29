#!/usr/bin/env python
"""Static release-contract verification for M77.0.3."""
from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _read(relative: str) -> str:
    return (ROOT / relative).read_text()


def main() -> int:
    repository = _read("src/trading_ai/institutional_options/repository.py")
    valuation = _read("src/trading_ai/institutional_options/valuation.py")
    management = _read("src/trading_ai/institutional_options/management.py")
    decision = _read("src/trading_ai/institutional_options/decision.py")
    ingestion = _read("scripts/ingestion_split_common.py")
    recovery = _read(
        "scripts/run_m77_0_3_recover_institutional_options_requalification.py"
    )

    checks = {
        "selection_replaced_exactly": (
            "existing.selected = bool(candidate.selected)" in repository
            and "existing.selected or candidate.selected" not in repository
        ),
        "comparison_is_strategy_authority": all(
            token in management
            for token in (
                "StrategyComparisonModel",
                "selected_strategy_candidate_id",
                "_authoritative_strategy_row",
            )
        ),
        "current_option_snapshot_contract_only": all(
            token in management + valuation + decision
            for token in (
                "option_snapshot_id",
                "Current governed option snapshot lineage is missing",
                "current option snapshot",
            )
        ),
        "execution_contract_is_decision_authority": (
            "contract_recommendation_id=execution.contract_recommendation_id"
            in decision
        ),
        "prerequisite_failures_are_visible": all(
            token in decision
            for token in (
                "prerequisite_requested",
                "valuation_failed",
                "management_failed",
                "remaining_contracts_optimized",
                "prerequisite_errors",
            )
        ),
        "ingestion_reports_failure_telemetry": all(
            token in ingestion
            for token in (
                "valuation_failed",
                "management_failed",
                "remaining_contracts_optimized",
            )
        ),
        "certification_failure_is_terminal": all(
            token in management
            for token in (
                "OpportunityState.REJECTED",
                "Final Institutional Options plan failed certification",
                "rejected += 1",
            )
        ),
        "history_is_preserved": (
            ".delete(" not in repository
            and ".delete(" not in valuation
            and ".delete(" not in management
            and '"historical_rows_deleted": 0' in recovery
        ),
        "recovery_is_current_run_only": all(
            token in recovery
            for token in (
                "latest_stock_scanner_run_id",
                "InstitutionalOpportunityModel.stock_scanner_run_id",
                "== stock_scanner_run_id",
                "OpportunityState.CONTRACTS_OPTIMIZED.value",
            )
        ),
        "recovery_is_serialized_bounded_and_resumable": all(
            token in recovery
            for token in (
                "pg_try_advisory_lock",
                "pg_advisory_unlock",
                "BUSY_EXIT = 75",
                "--batch-size",
                "--max-batches",
                "session.commit()",
                "attempted",
            )
        ),
    }
    result = {
        "version": "M77.0.3-STATIC-RELEASE-VERIFICATION-1.0",
        "status": "PASSED" if all(checks.values()) else "FAILED",
        "checks": checks,
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["status"] == "PASSED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
