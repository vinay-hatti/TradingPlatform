from __future__ import annotations

from typing import Any


def _dict(value: Any) -> dict:
    return dict(value or {}) if isinstance(value, dict) else {}


def _reasons(execution_payload: dict) -> list[str]:
    authority = _dict(execution_payload.get("trade_builder_authority"))
    certification = _dict(execution_payload.get("trade_plan_certification"))
    entry = _dict(authority.get("entry_execution") or certification.get("entry_execution"))
    values = authority.get("reason_codes") or entry.get("reason_codes") or []
    return [str(item) for item in values if str(item).strip()]


def derive_lifecycle_authority(
    *,
    recorded_state: str,
    selected_valuation: bool,
    executable_contract: bool,
    execution_payload: dict | None,
    execution_ready: bool | None,
    management_present: bool,
    decision_present: bool,
    portfolio_decision: dict | None = None,
) -> dict:
    """Derive current workflow completion independently from entry/portfolio authority.

    The persisted opportunity state is intentionally retained as audit history.  This
    projection prevents a coarse CONTRACTS_OPTIMIZED state from falsely implying
    that valuation, selection, management, or decision work is still missing.
    """
    execution = _dict(execution_payload)
    authority = _dict(execution.get("trade_builder_authority"))
    certification = _dict(execution.get("trade_plan_certification"))
    portfolio = _dict(portfolio_decision)
    optimizer = _dict(portfolio.get("optimizer_selection"))

    execution_disposition = str(
        authority.get("execution_disposition")
        or certification.get("execution_disposition")
        or _dict(certification.get("entry_execution")).get("disposition")
        or ""
    ).upper()
    reason_codes = _reasons(execution)

    artifacts = {
        "selected_valuation": bool(selected_valuation),
        "executable_contract": bool(executable_contract),
        "execution_recommendation": bool(execution),
        "management_plan": bool(management_present),
        "decision_snapshot": bool(decision_present),
    }
    plan_complete = all(artifacts.values())

    if not selected_valuation:
        next_action = "Value the alternatives and select the governed strategy winner."
        display_state = recorded_state
    elif not executable_contract:
        next_action = "Re-optimize exact Polygon contracts for the selected strategy."
        display_state = recorded_state
    elif not management_present:
        next_action = "Build the governed management plan for the selected strategy and contract."
        display_state = recorded_state
    elif not decision_present:
        next_action = "Build the institutional decision snapshot from the completed valuation and management plan."
        display_state = recorded_state
    elif not execution:
        next_action = "Rebuild the execution recommendation for the completed institutional plan."
        display_state = "PLAN_COMPLETE_EXECUTION_REBUILD_REQUIRED"
    elif execution_disposition == "WAITING_FOR_ENTRY":
        next_action = "Wait for the governed entry condition; do not chase the trade."
        display_state = "PLAN_COMPLETE_WAITING_FOR_ENTRY"
    elif execution_disposition == "REGENERATE_REQUIRED":
        next_action = "Regenerate the trade geometry at the current market before reconsidering execution."
        display_state = "PLAN_COMPLETE_REGENERATE_REQUIRED"
    elif execution_ready is not True:
        next_action = "Resolve the current certified execution block before Trade Builder handoff."
        display_state = "PLAN_COMPLETE_ENTRY_BLOCKED"
    else:
        portfolio_decision_value = str(portfolio.get("decision") or "").upper()
        lifecycle_current = str(_dict(portfolio.get("lifecycle")).get("status") or "").upper() == "CURRENT"
        selected = optimizer.get("optimality_proven") is True and optimizer.get("selected") is True and optimizer.get("status") == "SELECTED_GLOBAL_FEASIBLE"
        not_selected = optimizer.get("optimality_proven") is True and optimizer.get("selected") is False and optimizer.get("status") == "NOT_SELECTED_GLOBAL_FEASIBLE"
        if not portfolio:
            next_action = "Rebuild current portfolio authority before Trade Builder handoff."
            display_state = "PLAN_COMPLETE_AWAITING_PORTFOLIO_AUTHORITY"
        elif portfolio_decision_value not in {"ACCEPT", "REVIEW"}:
            next_action = "Portfolio governance currently blocks this completed trade plan."
            display_state = "PLAN_COMPLETE_PORTFOLIO_BLOCKED"
        elif not lifecycle_current:
            next_action = "Rebuild stale portfolio authority before Trade Builder handoff."
            display_state = "PLAN_COMPLETE_PORTFOLIO_AUTHORITY_STALE"
        elif selected:
            next_action = "Open Trade Builder for final review and governed handoff."
            display_state = "READY_FOR_EXECUTION"
        elif not_selected:
            next_action = "No handoff: this executable plan was not selected by the current global portfolio optimum."
            display_state = "PLAN_COMPLETE_NOT_SELECTED"
        else:
            next_action = "Rebuild optimizer-selection authority before Trade Builder handoff."
            display_state = "PLAN_COMPLETE_AWAITING_OPTIMIZER_AUTHORITY"

    return {
        "version": "M68.2.1.15.4-AUTHORITY-STATE-RECONCILIATION-1.0",
        "recorded_state": str(recorded_state),
        "display_state": display_state,
        "plan_complete": plan_complete,
        "artifacts": artifacts,
        "execution_disposition": execution_disposition or None,
        "execution_reason_codes": reason_codes,
        "next_governed_action": next_action,
    }
