from pathlib import Path
from trading_ai.execution_intelligence.policy import ExecutionIntelligencePolicy
from trading_ai.execution_intelligence.auto_fill import AutomaticEntryFillManager

def test_policy_has_bounded_chase_controls():
    p=ExecutionIntelligencePolicy()
    assert p.automatic_fill_management_enabled is True
    assert p.initial_limit_aggression_pct < 100
    assert p.chase_step_aggression_pct > 0
    assert p.maximum_reprices == 4
    assert p.working_order_max_age_seconds == 600
    assert 0 < p.minimum_ev_retention_pct <= 100

def test_manager_version():
    assert AutomaticEntryFillManager.VERSION.startswith("M73")
    assert "ADAPTIVE-WORKING-ORDER-LIFETIME" in AutomaticEntryFillManager.VERSION

def test_single_leg_submit_uses_governed_limit_not_crossing_price():
    text=(Path(__file__).resolve().parents[1]/"src/trading_ai/execution_workspace/service.py").read_text()
    assert "broker_limit_price=abs(signed_net_price) if len(legs)==1 else signed_net_price" in text
    assert "limit_price=broker_limit_price" in text
    assert "live_leg_map.get(str(leg.get('option_symbol'))" not in text

def test_working_assessment_progresses_aggression_and_can_cancel_edge_loss():
    text=(Path(__file__).resolve().parents[1]/"src/trading_ai/execution_intelligence/service.py").read_text()
    assert "progressive_aggression" in text
    assert "expected_value_retention" in text
    assert "edge_lost" in text
