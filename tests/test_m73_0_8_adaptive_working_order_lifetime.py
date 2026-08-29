from trading_ai.execution_intelligence.entry_chase import working_order_lifetime_phase
from trading_ai.execution_intelligence.policy import ExecutionIntelligencePolicy

def test_default_windows():
    p=ExecutionIntelligencePolicy()
    assert p.active_chase_window_seconds==180.0
    assert p.working_order_max_age_seconds==600.0

def test_active_chase_before_180():
    assert working_order_lifetime_phase(120,180,600)['phase']=='ACTIVE_CHASE'

def test_180_is_resting_not_cancel():
    x=working_order_lifetime_phase(180,180,600)
    assert x['phase']=='RESTING'
    assert x['reason']=='RESTING_AT_FINAL_LIMIT'
    assert x['cancel_required'] is False

def test_181_is_resting_not_cancel():
    assert working_order_lifetime_phase(181,180,600)['cancel_required'] is False

def test_600_boundary_still_resting():
    assert working_order_lifetime_phase(600,180,600)['phase']=='RESTING'

def test_after_600_is_hard_timeout():
    x=working_order_lifetime_phase(600.01,180,600)
    assert x['phase']=='HARD_TIMEOUT'
    assert x['cancel_required'] is True

def test_invalid_windows_fail():
    import pytest
    with pytest.raises(ValueError): working_order_lifetime_phase(10,601,600)
