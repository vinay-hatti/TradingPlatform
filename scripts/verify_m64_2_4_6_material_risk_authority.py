#!/usr/bin/env python
"""Static verification for M64.2.4.6 material risk authority."""
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
        ROOT / "tests/test_m64_2_4_6_material_risk_authority.py"
    ).read_text()

    checks = {
        "explicit_semantic_projection": all(
            token in service for token in (
                "def semantic_projection",
                "MATERIALITY_POLICY",
                "EXPIRATION_GUARD_SEMANTIC_FIELDS",
                "_position_projection",
                "_structure_projection",
            )
        ),
        "observed_jitter_banded": all(
            token in service for token in (
                '"risk_currency": 10.0',
                '"portfolio_greek": 1.0',
                '"position_greek": 1.0',
                '"volatility": 0.01',
                '"beta_weighted_delta_currency": 100.0',
            )
        ),
        "structural_leg_identity": all(
            token in service for token in (
                "_position_identity(positions[index])",
                '"legs": legs',
            )
        ) and '"leg_indexes":' not in service.split(
            "def _structure_projection", 1
        )[1].split("def semantic_projection", 1)[0],
        "guard_semantics_allow_listed": all(
            token in service for token in (
                '"exit_on_or_before_date"',
                '"mandatory_exit"',
                '"management_generation"',
                '"armed_at"',
            )
        ),
        "semantic_and_integrity_separated": all(
            token in service for token in (
                "def state_integrity_fingerprint",
                'payload["state_integrity_fingerprint"]',
            )
        ) and any(
            token in service for token in (
                "M64.2.4.6-MATERIAL-RISK-AUTHORITY-1.0",
                "M64.2.4.7-BASELINE-MATERIAL-RISK-AUTHORITY-1.0",
            )
        ) and any(
            token in service for token in (
                "M64.2.4.6-EXACT-RISK-SNAPSHOT-INTEGRITY-1.0",
                "M64.2.4.7-EXACT-RISK-SNAPSHOT-INTEGRITY-1.0",
            )
        ),
        "exact_integrity_fail_closed": all(
            token in orchestration for token in (
                "published_risk_integrity_fingerprint",
                "computed_published_risk_integrity_fingerprint",
                "PortfolioRiskAllocationService.state_integrity_fingerprint",
                "risk_fingerprint_integrity",
            )
        ),
        "authority_version_advanced": any(
            token in orchestration for token in (
                "M64.2.4.6-AUTHORITY-INPUT-FINGERPRINT-1.0",
                "M64.2.4.7-AUTHORITY-INPUT-FINGERPRINT-1.0",
            )
        ),
        "cycle_version_advanced": any(
            token in orchestration for token in (
                "M64.2.4.6-UNCHANGED-AUTHORITY-CYCLE-1.0",
                "M64.2.4.7-BASELINE-MATERIALITY-CYCLE-1.0",
            )
        ),
        "scheduler_version_advanced": (
            "skip_unchanged_authority=not force_authoritative_rebuild"
            in scheduler
            and any(token in scheduler for token in (
                "M64.2.4.6-SCHEDULED-PROGRESS-1.0",
                "M64.2.4.7-SCHEDULED-PROGRESS-1.0",
            ))
            and any(token in scheduler for token in (
                "M64.2.4.6-SCHEDULED-CYCLE-1.0",
                "M64.2.4.7-SCHEDULED-CYCLE-1.0",
            ))
        ),
        "production_diagnostic_regression": all(
            token in tests for token in (
                "test_observed_numeric_jitter_is_not_new_authority",
                "12_491.978807607167",
                "12_491.950740317716",
                "310_993.2040662526",
                "310_993.17826239276",
                "test_structure_leg_indexes_are_replaced_by_stable_leg_identity",
                "test_uncontracted_operational_telemetry_cannot_enter_authority",
            )
        ),
        "substantive_changes_governed": all(
            token in tests for token in (
                "test_substantive_portfolio_and_risk_changes_cross_authority",
                '"quantity"] = 2.0',
                '"exit_on_or_before_date"',
                '"option_mark"] = 10.25',
                '"delta"] = 802.0',
            )
        ),
        "operator_rebuild_default_preserved": (
            "skip_unchanged_authority: bool = False" in orchestration
        ),
    }
    passed = all(checks.values())
    print(json.dumps({
        "checks": checks,
        "status": "PASSED" if passed else "FAILED",
        "version": "M64.2.4.6-STATIC-RELEASE-VERIFICATION-1.0",
    }, indent=2, sort_keys=True))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
