#!/usr/bin/env python
"""Static release verification for M64.2.4.4 unchanged-authority no-op."""
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
    optimizer = (
        ROOT / "src/trading_ai/portfolio_risk_allocation/optimizer.py"
    ).read_text()
    scheduler = (
        ROOT / "scripts/run_m64_portfolio_intelligence.py"
    ).read_text()

    checks = {
        "transient_risk_preflight": all(token in service for token in (
            "persist: bool = True",
            "if persist:",
            "def persist(self, snapshot: dict)",
        )),
        "semantic_risk_fingerprint": (
            all(token in service for token in (
                'payload.pop("generated_by", None)',
                'payload.pop("semantic_fingerprint", None)',
                '"net_liquidation"',
                '"portfolio_heat_pct"',
            ))
            or all(token in service for token in (
                "def semantic_projection",
                "MATERIALITY_POLICY",
                "def state_integrity_fingerprint",
                '"net_liquidation"',
                '"portfolio_heat_pct"',
            ))
        ) and any(
            version in service
            for version in (
                "M64.2.4.4-RISK-SEMANTIC-FINGERPRINT-1.0",
                "M64.2.4.5-RISK-SEMANTIC-FINGERPRINT-1.0",
                "M64.2.4.6-MATERIAL-RISK-AUTHORITY-1.0",
                "M64.2.4.7-BASELINE-MATERIAL-RISK-AUTHORITY-1.0",
            )
        ),
        "complete_authority_fingerprint": all(
            token in orchestration for token in (
                "institutional_decision_set_fingerprint",
                "correlation_input_fingerprint",
                "optimizer_position_fingerprint",
                "PortfolioOptimizationService.DEFAULT_POLICY",
            )
        ) and any(
            version in orchestration
            for version in (
                "M64.2.4.4-AUTHORITY-INPUT-FINGERPRINT-1.0",
                "M64.2.4.5-AUTHORITY-INPUT-FINGERPRINT-1.0",
                "M64.2.4.6-AUTHORITY-INPUT-FINGERPRINT-1.0",
                "M64.2.4.7-AUTHORITY-INPUT-FINGERPRINT-1.0",
            )
        ),
        "fail_closed_authority_validation": all(
            token in orchestration for token in (
                "fingerprint_matches",
                "risk_fingerprint_integrity",
                "optimization_snapshot_matches",
                "portfolio_decisions_current",
                "embedded_decisions_current",
                'status = "VALID" if all(checks.values()) else "INVALID"',
            )
        ),
        "atomic_publication_records_fingerprint": all(
            token in optimizer for token in (
                "authority_input: dict | None = None",
                '"authority_input": dict(authority_input or {})',
            )
        ),
        "no_op_precedes_materialization": (
            orchestration.index("if unchanged_authority:")
            < orchestration.index('"decision_generation_started"')
        ),
        "no_op_retains_history_governance": all(
            token in orchestration for token in (
                "cycle_noop_unchanged_authority",
                "_prune_expired_history",
                '"superseded_decision_count": 0',
                '"authoritative_rebuild_performed": False',
                '"cycle_outcome": "NO_CHANGE"',
            )
        ),
        "scheduled_default_no_op": all(token in scheduler for token in (
            "force_authoritative_rebuild: bool = False",
            "skip_unchanged_authority=not force_authoritative_rebuild",
            "--force-authoritative-rebuild",
        )),
        "operator_default_rebuild": (
            "skip_unchanged_authority: bool = False" in orchestration
        ),
    }
    passed = all(checks.values())
    print(json.dumps({
        "checks": checks,
        "status": "PASSED" if passed else "FAILED",
        "version": "M64.2.4.4-STATIC-RELEASE-VERIFICATION-1.0",
    }, indent=2, sort_keys=True))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
