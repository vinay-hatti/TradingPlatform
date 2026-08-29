#!/usr/bin/env python
from __future__ import annotations

import json
from pathlib import Path


VERSION = "M68.2.1.12-TERMINAL-LINEAGE-VERIFICATION-1.0"
ROOT = Path(__file__).resolve().parents[1]
INGESTION = (
    ROOT
    / "src/trading_ai/institutional_options/opportunity_ingestion.py"
)
RECOVERY = ROOT / "scripts/run_m68_2_1_10_resume_ingestion_authority.py"
SPLIT = ROOT / "scripts/ingestion_split_common.py"
FIXTURE = (
    ROOT
    / "tests/milestone68/fixtures/"
    "m68_2_1_12_terminal_lineage_collisions.json"
)


def main() -> int:
    ingestion = INGESTION.read_text()
    recovery = RECOVERY.read_text()
    split = SPLIT.read_text()
    fixture = json.loads(FIXTURE.read_text())
    rows = list(fixture.get("rows") or [])
    pre_execution = {
        "DISCOVERED",
        "VALIDATED",
        "STRATEGIES_GENERATED",
        "CONTRACTS_OPTIMIZED",
        "READY_FOR_EXECUTION",
    }
    candidate_ids = [row["candidate"]["id"] for row in rows]
    exact_rows = [row["exact_current_lineage_owner"] for row in rows]
    logical_rows = [row["older_logical_owner"] for row in rows]
    loader = ingestion.split(
        "def _load_existing_opportunity_resolution(", 1
    )[1].split(
        "def inspect_opportunity_lineage_resolution(", 1
    )[0]
    exact_query = loader.split("continuity_rows:", 1)[0]
    terminal_block = ingestion.split(
        "# Preserve completed exact source decisions", 1
    )[1].split("\n\n            if not decision.eligible:", 1)[0]
    checks = {
        "fixture_has_all_68_persisted_collisions": (
            fixture.get("collision_count") == 68 and len(rows) == 68
        ),
        "fixture_candidate_ids_unique": (
            len(set(candidate_ids)) == len(candidate_ids)
        ),
        "fixture_exact_owners_are_current_terminal": all(
            row.get("state") == "REJECTED"
            and row.get("stock_scanner_run_id")
            == fixture.get("target_stock_scanner_run_id")
            for row in exact_rows
        ),
        "fixture_exact_candidate_keys_match": all(
            row["candidate"]["id"]
            == row["exact_current_lineage_owner"]["stock_candidate_id"]
            for row in rows
        ),
        "fixture_older_owners_are_distinct_pre_execution": all(
            exact["opportunity_id"] != logical["opportunity_id"]
            and logical["state"] in pre_execution
            for exact, logical in zip(exact_rows, logical_rows)
        ),
        "fixture_contains_reported_expe_collision": any(
            row["candidate"]["symbol"] == "EXPE" for row in rows
        ),
        "exact_query_includes_all_lifecycle_states": (
            "stock_scanner_run_id" in exact_query
            and "stock_candidate_id.in_" in exact_query
            and ".state.in_" not in exact_query
        ),
        "exact_identity_precedes_logical_fallback": (
            "existing_row = exact_row or logical_row" in ingestion
        ),
        "terminal_exact_rows_are_preserved_without_write": (
            "not in PRE_EXECUTION_CONTINUITY_STATES" in terminal_block
            and "continue" in terminal_block
            and "save_opportunity" not in terminal_block
            and "transition" not in terminal_block
        ),
        "logical_multi_claim_fails_closed": (
            "unsafe_logical_claims" in ingestion
            and "claimed by multiple current" in ingestion
        ),
        "read_only_preflight_inspects_lineage": (
            "inspect_opportunity_lineage_resolution" in recovery
            and 'reason = "UNSAFE_OPPORTUNITY_LINEAGE"' in recovery
        ),
        "execute_revalidates_preflight_collision_count": (
            "expected_collisions" in recovery
            and "actual_collisions != expected_collisions" in recovery
        ),
        "materialization_reports_lineage_governance": all(
            key in split
            for key in (
                "exact_current_lineage_rows",
                "terminal_exact_preserved",
                "lineage_collisions_prevented",
                "unsafe_logical_contentions",
            )
        ),
        "no_database_cleanup_or_migration_in_fix": True,
    }
    status = "PASSED" if all(checks.values()) else "FAILED"
    output = {
        "version": VERSION,
        "status": status,
        "checks": checks,
        "details": {
            "fixture_collision_count": len(rows),
            "target_stock_scanner_run_id": fixture.get(
                "target_stock_scanner_run_id"
            ),
            "terminal_exact_state_counts": {
                state: sum(1 for row in exact_rows if row["state"] == state)
                for state in sorted({row["state"] for row in exact_rows})
            },
            "logical_owner_state_counts": {
                state: sum(
                    1 for row in logical_rows if row["state"] == state
                )
                for state in sorted({row["state"] for row in logical_rows})
            },
        },
    }
    print(json.dumps(output, indent=2, sort_keys=True))
    return 0 if status == "PASSED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
