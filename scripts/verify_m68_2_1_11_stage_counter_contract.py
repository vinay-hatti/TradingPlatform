#!/usr/bin/env python
from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def contains(path: str, *needles: str) -> bool:
    source = (ROOT / path).read_text()
    return all(needle in source for needle in needles)


def main() -> int:
    checks = {
        "versioned_opportunity_deserializer": contains(
            "src/trading_ai/institutional_options/domain.py",
            "class InstitutionalOpportunity:",
            "def from_payload(",
            "inflection_intelligence",
            "intelligence_extensions",
        ),
        "valuation_uses_versioned_boundary": contains(
            "src/trading_ai/institutional_options/valuation.py",
            "InstitutionalOpportunity.from_payload(",
        ),
        "ready_prerequisite_reconciliation": contains(
            "src/trading_ai/institutional_options/decision.py",
            "def _ready_chain_is_complete(",
            "invalidate_ready_for_execution(",
            "M68.2.1.10-DECISION-PREREQUISITES-1.0",
        ),
        "conditional_entry_governed": contains(
            "src/trading_ai/institutional_options/decision.py",
            "governed_not_ready",
            'disposition != "READY_NOW"',
        ),
        "advancement_counts_non_actionable_governance": contains(
            "scripts/ingestion_split_common.py",
            'summary["governed_not_ready"]',
            "+ summary[\"governed_not_ready\"]",
        ),
        "stage_counter_namespaces_separated": contains(
            "scripts/ingestion_split_common.py",
            "_CLASSIFIED_ADVANCEMENT_COUNTERS",
            "_RESULT_ADVANCEMENT_COUNTERS",
            "def merge_advancement_stage_counters(",
            "classified_counts=classified_counts",
        ),
        "result_counters_initialized": contains(
            "scripts/ingestion_split_common.py",
            '"governed_not_ready": 0',
            '"reconciled_ready": 0',
        ),
        "unsafe_cross_index_removed": (
            "summary[key] += counts[key]"
            not in (
                ROOT / "scripts/ingestion_split_common.py"
            ).read_text()
        ),
        "authority_records_non_actionable_governance": contains(
            "src/trading_ai/institutional_options/advancement_authority.py",
            '"governed_not_ready"',
        ),
        "partial_recovery_is_resumable": contains(
            "scripts/run_m68_2_1_10_resume_ingestion_authority.py",
            "RESUME_PARTIAL_ADVANCEMENT",
            "advancement_fingerprint",
            "LATEST_AUTHORITY_ALREADY_COMPLETE",
        ),
        "resume_keeps_m64_last": (
            (
                ROOT
                / "scripts/run_m68_2_1_10_resume_ingestion_authority.py"
            ).read_text().index("advance_institutional_options_workflow(")
            < (
                ROOT
                / "scripts/run_m68_2_1_10_resume_ingestion_authority.py"
            ).read_text().index(
                "Milestone64ContinuousPortfolioIntelligenceService"
                "(SessionLocal).run("
            )
        ),
    }
    result = {
        "version": (
            "M68.2.1.11-STAGE-COUNTER-CONTRACT-VERIFICATION-1.0"
        ),
        "status": "PASSED" if all(checks.values()) else "FAILED",
        "checks": checks,
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["status"] == "PASSED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
