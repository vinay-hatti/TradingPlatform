from trading_ai.execution_intelligence.entry_chase import adaptive_chase_state
from trading_ai.execution_intelligence.policy import ExecutionIntelligencePolicy


def _state(**overrides):
    args=dict(
        current_price=7.57,
        fresh_executable_price=7.60,
        frozen_boundary_price=8.56,
        age_seconds=90,
        active_chase_window_seconds=180,
        maximum_working_order_age_seconds=900,
        reprice_count=4,
        fast_reprice_limit=4,
        adaptive_enabled=True,
    )
    args.update(overrides)
    return adaptive_chase_state(**args)


def test_uso_shape_continues_after_four_reprices_when_market_room_remains():
    x=_state()
    assert x['phase']=='ADAPTIVE_CHASE'
    assert x['needs_chase'] is True
    assert abs(x['target_price']-7.60)<1e-9


def test_fast_phase_is_preserved_before_fast_limit():
    x=_state(reprice_count=2, age_seconds=60)
    assert x['phase']=='ACTIVE_CHASE'
    assert x['needs_chase'] is True


def test_after_active_window_moves_to_adaptive_not_resting_when_room_remains():
    x=_state(reprice_count=2, age_seconds=240)
    assert x['phase']=='ADAPTIVE_CHASE'


def test_buy_debit_rests_when_fresh_executable_is_reached():
    x=_state(current_price=7.60)
    assert x['phase']=='RESTING'
    assert x['reason']=='EXECUTABLE_PRICE_REACHED'


def test_buy_debit_never_targets_beyond_maximum_debit():
    x=_state(current_price=8.50, fresh_executable_price=9.25, frozen_boundary_price=8.56)
    assert x['phase']=='ADAPTIVE_CHASE'
    assert abs(x['target_price']-8.56)<1e-9
    y=_state(current_price=8.56, fresh_executable_price=9.25, frozen_boundary_price=8.56)
    assert y['phase']=='RESTING'
    assert y['reason']=='FROZEN_BOUNDARY_REACHED'


def test_sell_credit_reverse_chase_moves_signed_price_toward_zero():
    # SELL broker limits are represented in signed economic terms by assess_working:
    # $3.00 credit => -3.00, $2.80 executable credit => -2.80.
    x=_state(current_price=-3.00, fresh_executable_price=-2.80, frozen_boundary_price=-2.75)
    assert x['phase']=='ADAPTIVE_CHASE'
    assert abs(x['target_price']-(-2.80))<1e-9
    assert x['target_price'] > -3.00


def test_sell_credit_never_accepts_less_than_frozen_minimum_credit():
    x=_state(current_price=-3.00, fresh_executable_price=-2.60, frozen_boundary_price=-2.75)
    assert x['phase']=='ADAPTIVE_CHASE'
    assert abs(x['target_price']-(-2.75))<1e-9
    y=_state(current_price=-2.75, fresh_executable_price=-2.60, frozen_boundary_price=-2.75)
    assert y['phase']=='RESTING'
    assert y['reason']=='FROZEN_BOUNDARY_REACHED'


def test_hard_timeout_still_cancels():
    x=_state(age_seconds=900.01)
    assert x['phase']=='HARD_TIMEOUT'
    assert x['cancel_required'] is True


def test_policy_defaults_enable_slower_adaptive_phase():
    p=ExecutionIntelligencePolicy()
    assert p.maximum_reprices==4
    assert p.adaptive_chase_enabled is True
    assert p.adaptive_modify_interval_seconds==45.0
