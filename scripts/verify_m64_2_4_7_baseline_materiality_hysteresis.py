#!/usr/bin/env python
"""Static verification for M64.2.4.7 sticky-baseline materiality."""
from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    service = (
        ROOT / "src/trading_ai/portfolio_risk_allocation/service.py"
    ).read_text()
    orchestration = (
        ROOT / "src/trading_ai/portfolio_risk_allocation/orchestration.py"
    ).read_text()
    scheduler = (
        ROOT / "scripts/run_m64_portfolio_intelligence.py"
    ).read_text()
    tests = (
        ROOT / "tests/test_m64_2_4_7_baseline_materiality_hysteresis.py"
    ).read_text()

    checks = {
        "baseline_relative_comparator": all(
            token in service for token in (
                "M64.2.4.7-BASELINE-RELATIVE-MATERIALITY-1.0",
                "def materiality_projection",
                "def materiality_evaluation",
                "delta < threshold",
                '"status": "EQUIVALENT" if equivalent',
            )
        ),
        "rounding_boundary_regression": all(
            token in tests for token in (
                "test_rounding_boundary_does_not_create_material_authority",
                "_snapshot(10.024)",
                "_snapshot(10.026)",
                'evaluation["status"] == "EQUIVALENT"',
            )
        ),
        "material_change_regression": all(
            token in tests for token in (
                "test_material_numeric_change_crosses_sticky_baseline",
                "_snapshot(10.08)",
                'evaluation["status"] == "MATERIAL_CHANGE"',
                "test_structural_position_change_crosses_sticky_baseline",
            )
        ),
        "sticky_published_baseline": all(
            token in orchestration for token in (
                "current_publication.risk_snapshot_id",
                "baseline_risk = {",
                "resolve_material_authority",
                '"_risk_materiality": risk_materiality',
            )
        ),
        "effective_semantics_reused": all(
            token in service for token in (
                "BASELINE_EQUIVALENT",
                '"effective_semantic_fingerprint": baseline_semantic',
                '"reuse_published_semantics": True',
            )
        ),
        "exact_integrity_fail_closed": all(
            token in service for token in (
                "CANDIDATE_INTEGRITY_INVALID",
                "BASELINE_INTEGRITY_INVALID",
                "state_integrity_fingerprint",
            )
        ) and all(
            token in orchestration for token in (
                "candidate_integrity_valid",
                "risk_fingerprint_integrity",
            )
        ),
        "materiality_diagnostics": all(
            token in orchestration for token in (
                "risk_materiality_status",
                "baseline_risk_snapshot_id",
                "suppressed_submaterial_change_count",
                "material_numeric_change_count",
                "structural_change_count",
            )
        ),
        "authority_versions_advanced": all(
            token in service + orchestration + scheduler for token in (
                "M64.2.4.7-BASELINE-MATERIAL-RISK-AUTHORITY-1.0",
                "M64.2.4.7-EXACT-RISK-SNAPSHOT-INTEGRITY-1.0",
                "M64.2.4.7-AUTHORITY-INPUT-FINGERPRINT-1.0",
                "M64.2.4.7-BASELINE-MATERIALITY-CYCLE-1.0",
                "M64.2.4.7-SCHEDULED-PROGRESS-1.0",
                "M64.2.4.7-SCHEDULED-CYCLE-1.0",
            )
        ),
        "operator_rebuild_default_preserved": (
            "skip_unchanged_authority: bool = False" in orchestration
        ),
        "scheduled_noop_default_preserved": (
            "skip_unchanged_authority=not force_authoritative_rebuild"
            in scheduler
        ),
    }
    passed = all(checks.values())
    print(json.dumps({
        "checks": checks,
        "status": "PASSED" if passed else "FAILED",
        "version": "M64.2.4.7-STATIC-RELEASE-VERIFICATION-1.0",
    }, indent=2, sort_keys=True))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
