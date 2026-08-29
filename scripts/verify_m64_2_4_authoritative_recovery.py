#!/usr/bin/env python
"""Read-only production acceptance gate after M64.2.4 regeneration."""
from __future__ import annotations

import argparse
import json

from run_m76_2_4_portfolio_governance_audit import audit


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Verify current M64 authority, risk, and expiration governance"
    )
    parser.add_argument("--portfolio-id", default="PAPER-PRIMARY")
    args = parser.parse_args()
    report = audit(args.portfolio_id)
    authority = dict(report.get("decision_authority") or {})
    risk = dict(report.get("risk_snapshot") or {})
    operational = dict(risk.get("operational_risk") or {})
    eligible = int(report.get("current_ready_for_execution_candidates") or 0)
    materialized = int(report.get("current_portfolio_decisions") or 0)
    missing = int(report.get("missing_current_decisions") or 0)
    managed = int(operational.get("managed_option_positions") or 0)
    armed = int(operational.get("expiration_guards_armed") or 0)
    missing_guards = int(operational.get("missing_expiration_guards") or 0)
    checks = {
        "authority_current": authority.get("status") == "CURRENT",
        "publication_matches_current_stock_run": bool(
            report.get("diagnosis", {}).get("publication_matches_current_stock_run")
        ),
        "eligible_candidates_present": eligible > 0,
        "exact_decision_coverage": materialized == eligible and missing == 0,
        "capital_inputs_ready": risk.get("input_integrity") == "READY",
        "governed_risk_basis": (
            risk.get("trading_risk_basis")
            == "GOVERNED_PRE_EXPIRATION_DEFINED_LOSS"
        ),
        "expiration_governance_complete": (
            managed > 0 and armed == managed and missing_guards == 0
        ),
    }
    result = {
        "version": "M64.2.4-AUTHORITATIVE-RECOVERY-VERIFICATION-1.0",
        "portfolio_id": args.portfolio_id,
        "status": "PASSED" if all(checks.values()) else "FAILED",
        "checks": checks,
        "authority": authority,
        "eligible_candidates": eligible,
        "materialized_decisions": materialized,
        "missing_decisions": missing,
        "governed_open_risk": risk.get("open_risk"),
        "portfolio_heat_pct": risk.get("portfolio_heat_pct"),
        "expiration_guards": {
            "managed_positions": managed,
            "armed": armed,
            "missing": missing_guards,
        },
    }
    print(json.dumps(result, indent=2, sort_keys=True, default=str))
    return 0 if result["status"] == "PASSED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
