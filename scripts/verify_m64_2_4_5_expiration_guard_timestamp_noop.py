#!/usr/bin/env python
"""Static verification for M64.2.4.5 guard timestamp semantics."""
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
        ROOT / "tests/test_m64_2_4_5_expiration_guard_timestamp_noop.py"
    ).read_text()

    checks = {
        "diagnostic_root_cause_targeted": (
            all(token in service for token in (
                "EXPIRATION_GUARD_SEMANTIC_FIELDS",
                '"exit_on_or_before_date"',
                "_expiration_guard_projection",
            ))
            or all(token in service for token in (
                'guard = position.get("expiration_guard")',
                'guard.pop("updated_at", None)',
                "M73 refreshes the same exit instruction",
            ))
        ),
        "broad_timestamp_exclusion_forbidden": (
            'payload.pop("updated_at", None)' not in service
            and 'position.pop("updated_at", None)' not in service
        ),
        "substantive_guard_semantics_preserved": all(
            token in tests for token in (
                "exit_on_or_before_date",
                '"status"] = "CANCELLED"',
                '"expiration_guard_armed"',
            )
        ),
        "risk_contract_version_advanced": (
            any(version in service for version in (
                "M64.2.4.5-RISK-SEMANTIC-FINGERPRINT-1.0",
                "M64.2.4.6-MATERIAL-RISK-AUTHORITY-1.0",
                "M64.2.4.7-BASELINE-MATERIAL-RISK-AUTHORITY-1.0",
            ))
        ),
        "authority_contract_version_advanced": (
            any(version in orchestration for version in (
                "M64.2.4.5-AUTHORITY-INPUT-FINGERPRINT-1.0",
                "M64.2.4.6-AUTHORITY-INPUT-FINGERPRINT-1.0",
                "M64.2.4.7-AUTHORITY-INPUT-FINGERPRINT-1.0",
            ))
        ),
        "cycle_contract_version_advanced": (
            any(version in orchestration for version in (
                "M64.2.4.5-UNCHANGED-AUTHORITY-CYCLE-1.0",
                "M64.2.4.6-UNCHANGED-AUTHORITY-CYCLE-1.0",
                "M64.2.4.7-BASELINE-MATERIALITY-CYCLE-1.0",
            ))
        ),
        "scheduler_contract_version_advanced": (
            "skip_unchanged_authority=not force_authoritative_rebuild"
            in scheduler
            and any(version in scheduler for version in (
                "M64.2.4.5-SCHEDULED-PROGRESS-1.0",
                "M64.2.4.6-SCHEDULED-PROGRESS-1.0",
                "M64.2.4.7-SCHEDULED-PROGRESS-1.0",
            ))
            and any(version in scheduler for version in (
                "M64.2.4.5-SCHEDULED-CYCLE-1.0",
                "M64.2.4.6-SCHEDULED-CYCLE-1.0",
                "M64.2.4.7-SCHEDULED-CYCLE-1.0",
            ))
        ),
        "operator_rebuild_default_preserved": (
            "skip_unchanged_authority: bool = False" in orchestration
        ),
    }
    passed = all(checks.values())
    print(json.dumps({
        "checks": checks,
        "status": "PASSED" if passed else "FAILED",
        "version": "M64.2.4.5-STATIC-RELEASE-VERIFICATION-1.0",
    }, indent=2, sort_keys=True))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
