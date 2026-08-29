#!/usr/bin/env python
"""Static release-contract verification for M64.2.4.3."""
from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read(relative: str) -> str:
    return (ROOT / relative).read_text()


def main() -> int:
    governance = read(
        "src/trading_ai/portfolio_risk_allocation/history_governance.py"
    )
    orchestration = read(
        "src/trading_ai/portfolio_risk_allocation/orchestration.py"
    )
    operator = read(
        "scripts/run_m64_2_1_regenerate_current_portfolio_decisions.py"
    )
    scheduler = read("scripts/run_m64_portfolio_intelligence.py")
    wrapper = read(
        "scripts/run_m64_2_4_3_governed_purge_and_regenerate.py"
    )
    preflight = read("scripts/run_m64_2_4_3_purge_preflight.py")

    checks = {
        "explicit_confirmation": all(
            token in governance
            for token in (
                'CONFIRMATION_TOKEN = "PURGE-KNOWN-INVALID-M64-HISTORY"',
                "confirmation_token != self.CONFIRMATION_TOKEN",
                "raise PermissionError",
            )
        ),
        "postgresql_only": (
            'if dialect_name != "postgresql"' in governance
            and "requires PostgreSQL" in governance
        ),
        "inbound_fk_fail_closed": all(
            token in governance
            for token in (
                "FROM pg_constraint",
                "constraint_row.confrelid",
                "inbound foreign keys exist",
            )
        ),
        "protected_authority": all(
            token in governance
            for token in (
                "OTHER_PORTFOLIO",
                "PUBLISHED_RISK",
                "PINNED_RECOVERY_RISK",
                "DIRECT_REFERENCE:",
                "OPERATIONAL_OPPORTUNITY_LATEST:",
                "FORENSIC_BOUNDARY_SAMPLE:",
            )
        ),
        "pinned_risk_fail_closed": all(
            token in governance
            for token in (
                "requires a pinned risk snapshot",
                "portfolio_risk_allocation_snapshots",
                "target_risk_validation",
                "GOVERNED_PRE_EXPIRATION_DEFINED_LOSS",
                "failed governed READY ",
                "capital validation: ",
            )
        ),
        "transactional_relation_rebuild": all(
            token in governance
            for token in (
                "LOCK TABLE {source} IN SHARE MODE",
                "CREATE TEMP TABLE {protected_rows}",
                "TRUNCATE TABLE {source}",
                "INSERT INTO {source}",
                "session.commit()",
            )
        ) and "TRUNCATE TABLE {source} CASCADE" not in governance,
        "post_purge_invariants": all(
            token in governance
            for token in (
                "Post-purge total-row validation failed",
                "other-portfolio preservation validation failed",
                "Current publication changed during governed purge",
                "ANALYZE {source}",
            )
        ),
        "forensic_manifest": all(
            token in governance
            for token in (
                "protected_id_sha256",
                "manifest_sha256",
                "source_stats",
                "invalid_history_purge_committed",
            )
        ) and all(
            token in operator
            for token in (
                "_write_json_atomic",
                "os.fsync",
                "os.replace",
                "--purge-manifest-output",
            )
        ),
        "purge_precedes_authority": (
            orchestration.index("risk_snapshot_lookup_started")
            < orchestration.rindex("purge_known_invalid_history")
            < orchestration.index("decision_generation_started")
            and "compact_non_authoritative_history" not in orchestration
        ),
        "bounded_nonblocking_retention": all(
            token in governance
            for token in (
                "RETENTION_DAYS = 7",
                "RETENTION_BATCH_SIZE = 10_000",
                "FOR UPDATE OF decision SKIP LOCKED",
            )
        ) and all(
            token in orchestration
            for token in (
                "prune_expired_history",
                '"status": "DEFERRED_NON_BLOCKING"',
            )
        ),
        "operator_contract": all(
            token in operator
            for token in (
                "--confirm-purge-known-invalid-history",
                "m64-2-4-3-governed-purge-recovery",
                "M64.2.4.3-REGENERATION-PROGRESS-1.0",
            )
        ),
        "dedicated_wrapper": (
            "main(require_governed_purge=True)" in wrapper
        ),
        "read_only_preflight": all(
            token in governance
            for token in (
                "if dry_run:",
                '"status": "DRY_RUN_COMPLETE"',
                '"database_mutated": False',
                "session.rollback()",
            )
        ) and all(
            token in preflight
            for token in (
                "dry_run=True",
                "m64_2_4_3_purge_preflight.json",
                "_write_json_atomic",
            )
        ),
        "scheduler_has_no_cleanup_gate": (
            "M64HistoryCleanupIncompleteError" not in scheduler
            and any(
                version in scheduler
                for version in (
                    "M64.2.4.3-SCHEDULED-CYCLE-1.0",
                    "M64.2.4.4-SCHEDULED-CYCLE-1.0",
                    "M64.2.4.5-SCHEDULED-CYCLE-1.0",
                    "M64.2.4.6-SCHEDULED-CYCLE-1.0",
                    "M64.2.4.7-SCHEDULED-CYCLE-1.0",
                )
            )
        ),
    }
    result = {
        "version": "M64.2.4.3-STATIC-RELEASE-VERIFICATION-1.0",
        "status": "PASSED" if all(checks.values()) else "FAILED",
        "checks": checks,
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["status"] == "PASSED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
