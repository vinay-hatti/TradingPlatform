from pathlib import Path
from types import SimpleNamespace

from trading_ai.institutional_options.lifecycle_authority import derive_lifecycle_authority


def test_complete_plan_waiting_for_entry_does_not_claim_valuation_is_next():
    result = derive_lifecycle_authority(
        recorded_state="CONTRACTS_OPTIMIZED",
        selected_valuation=True,
        executable_contract=True,
        execution_payload={
            "trade_builder_authority": {
                "execution_disposition": "WAITING_FOR_ENTRY",
                "reason_codes": ["ABOVE_CHASE_LIMIT_WAIT_FOR_PULLBACK_OR_CONFIRMATION"],
            }
        },
        execution_ready=False,
        management_present=True,
        decision_present=True,
        portfolio_decision={},
    )
    assert result["plan_complete"] is True
    assert result["display_state"] == "PLAN_COMPLETE_WAITING_FOR_ENTRY"
    assert "Wait for the governed entry condition" in result["next_governed_action"]
    assert "Value the alternatives" not in result["next_governed_action"]


def test_complete_plan_regenerate_required_is_distinct_from_waiting():
    result = derive_lifecycle_authority(
        recorded_state="CONTRACTS_OPTIMIZED",
        selected_valuation=True,
        executable_contract=True,
        execution_payload={"trade_plan_certification": {"execution_disposition": "REGENERATE_REQUIRED"}},
        execution_ready=False,
        management_present=True,
        decision_present=True,
        portfolio_decision={},
    )
    assert result["display_state"] == "PLAN_COMPLETE_REGENERATE_REQUIRED"
    assert "Regenerate the trade geometry" in result["next_governed_action"]


def test_portfolio_context_reads_capital_from_valuation_payload_not_missing_column():
    source = Path("src/trading_ai/institutional_options/decision.py").read_text()
    assert 'valuation_payload.get("capital_required")' in source
    assert "valuation.capital_required" not in source


def test_router_projects_reconciled_state_without_mutating_recorded_state():
    source = Path("src/trading_ai/institutional_options/router.py").read_text()
    assert "derive_lifecycle_authority" in source
    assert 'payload["display_state"]' in source
    assert 'payload["next_governed_action"]' in source
    assert '"recorded_state": str(recorded_state)' in Path("src/trading_ai/institutional_options/lifecycle_authority.py").read_text()


def test_ui_uses_backend_next_governed_action_and_display_state():
    source = Path("ui/workstation/src/InstitutionalOptionsPage.tsx").read_text()
    assert "o.next_governed_action" in source
    assert "o.display_state" in source
    assert "PLAN_COMPLETE_WAITING_FOR_ENTRY" in source
    assert "PLAN_COMPLETE_REGENERATE_REQUIRED" in source
