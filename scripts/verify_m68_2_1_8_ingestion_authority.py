#!/usr/bin/env python
from __future__ import annotations

import argparse
import json
from pathlib import Path

from sqlalchemy import text

from trading_ai.database.session import SessionLocal
from trading_ai.institutional_options.advancement_authority import (
    validate_current_advancement_authority,
)


ROOT = Path(__file__).resolve().parents[1]
VERSION = "M68.2.1.8-INGESTION-AUTHORITY-VERIFICATION-1.0"


def static_checks() -> dict[str, bool]:
    domain = (ROOT / "src/trading_ai/institutional_options/domain.py").read_text()
    ingestion = (ROOT / "scripts/ingestion_split_common.py").read_text()
    orchestration = (
        ROOT / "src/trading_ai/portfolio_risk_allocation/orchestration.py"
    ).read_text()
    run_body = orchestration[orchestration.index("    def run("):]
    migration = (
        ROOT / "migrations/versions/m68_003_ingestion_authority_integrity.py"
    ).read_text()
    return {
        "migration_chain": (
            'revision = "m68_003"' in migration
            and 'down_revision = "m68_002"' in migration
        ),
        "coverage_status_capacity": "String(length=64)" in migration,
        "versioned_lineage_deserializer": (
            "source_option_snapshot_id" in domain
            and "contract_option_snapshot_id" in domain
            and "def from_payload" in domain
        ),
        "advancement_marker_lifecycle": (
            "invalidate_advancement_authority" in ingestion
            and "persist_advancement_authority" in ingestion
        ),
        "m64_pre_risk_gate": (
            run_body.index("validate_current_advancement_authority")
            < run_body.index("PortfolioRiskAllocationService")
        ),
        "m64_exact_current_baseline_preserved": (
            "M64.2.4.7-AUTHORITY-INPUT-FINGERPRINT-1.0" in orchestration
            and "M64.2.4.7-BASELINE-MATERIALITY-CYCLE-1.0"
            in orchestration
            and "cycle_noop_unchanged_authority" in orchestration
            and "suppressed_submaterial_change_count" in orchestration
        ),
        "orphan_retirement": "fail_unmaterialized_stock_publication" in ingestion,
        "runtime_progress_contract": (
            'diagnostics.get("disposition_counts")' in ingestion
            and "result.get('average_signal_strength', 0)" in ingestion
        ),
    }


def runtime_checks() -> tuple[dict[str, bool], dict]:
    authority = validate_current_advancement_authority(SessionLocal)
    run_id = authority["stock_scanner_run_id"]
    with SessionLocal() as session:
        details = dict(session.execute(text("""
            WITH latest_published AS (
                SELECT scanner_run_id
                  FROM stock_scanner_publications
                 WHERE publication_name = 'current_stock_intelligence'
                   AND status IN ('READY', 'DEGRADED')
                 ORDER BY snapshot_timestamp DESC
                 LIMIT 1
            ),
            inflection AS (
                SELECT source_run_id
                  FROM institutional_inflection_publications
                 WHERE publication_name = 'current_institutional_inflection'
            ),
            portfolio AS (
                SELECT payload_json::jsonb->>'stock_scanner_run_id' AS run_id
                  FROM portfolio_allocation_publications
                 WHERE portfolio_id = 'PAPER-PRIMARY'
                   AND publication_name = 'current_portfolio_allocation'
            )
            SELECT
                (SELECT scanner_run_id FROM latest_published) AS latest_stock_run,
                (SELECT source_run_id FROM inflection) AS inflection_run,
                (SELECT run_id FROM portfolio) AS portfolio_run,
                (
                    SELECT COUNT(*)
                      FROM stock_scanner_publications p
                     WHERE p.publication_name = 'current_stock_intelligence'
                       AND p.status IN ('READY', 'DEGRADED')
                       AND p.snapshot_timestamp > (
                           SELECT snapshot_timestamp
                             FROM stock_scanner_publications
                            WHERE publication_name = 'current_stock_intelligence'
                              AND scanner_run_id = :current_run_id
                       )
                       AND NOT EXISTS (
                           SELECT 1 FROM institutional_option_opportunities o
                            WHERE o.stock_scanner_run_id = p.scanner_run_id
                       )
                ) AS newer_usable_orphans,
                (
                    SELECT character_maximum_length
                      FROM information_schema.columns
                     WHERE table_name = 'institutional_inflection_snapshots'
                       AND column_name = 'coverage_status'
                ) AS snapshot_coverage_capacity,
                (
                    SELECT character_maximum_length
                      FROM information_schema.columns
                     WHERE table_name = 'institutional_inflection_publications'
                       AND column_name = 'coverage_status'
                ) AS publication_coverage_capacity
        """), {"current_run_id": run_id}).mappings().one())
    checks = {
        "advancement_authority_ready": authority["status"] == "READY",
        "latest_stock_run_aligned": details["latest_stock_run"] == run_id,
        "inflection_run_aligned": details["inflection_run"] == run_id,
        "portfolio_run_aligned": details["portfolio_run"] == run_id,
        "no_newer_usable_unmaterialized_publications": int(
            details["newer_usable_orphans"] or 0
        ) == 0,
        "snapshot_coverage_capacity_64": int(
            details["snapshot_coverage_capacity"] or 0
        ) == 64,
        "publication_coverage_capacity_64": int(
            details["publication_coverage_capacity"] or 0
        ) == 64,
    }
    return checks, {**details, "advancement_authority": authority}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--static-only", action="store_true")
    args = parser.parse_args()
    checks = static_checks()
    details: dict = {}
    if not args.static_only:
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
