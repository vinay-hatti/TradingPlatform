from trading_ai.execution_intelligence.entry_chase import advance_coarse_tick,monotonic_broker_candidate,same_price


def test_buy_chase_never_moves_backward():
    assert monotonic_broker_candidate('BUY',7.64,7.60)==7.64
    assert monotonic_broker_candidate('BUY',7.64,7.69)==7.69


def test_sell_chase_never_moves_backward():
    assert monotonic_broker_candidate('SELL',2.25,2.30)==2.25
    assert monotonic_broker_candidate('SELL',2.25,2.20)==2.20


def test_same_tick_is_noop_until_half_tick_crossed():
    r=advance_coarse_tick(side='BUY',current_price=.80,theoretical_price=.8237,normalized_price=.80,increment=.05,maximum_debit=.90,executable_price=.85)
    assert r['price']==.80 and not r['advanced'] and r['reason']=='WAIT_TICK_UNCHANGED'


def test_coarse_tick_advances_when_justified_and_inside_envelope():
    r=advance_coarse_tick(side='BUY',current_price=.80,theoretical_price=.835,normalized_price=.80,increment=.05,maximum_debit=.90,executable_price=.85)
    assert same_price(r['price'],.85) and r['advanced']


def test_coarse_tick_never_crosses_hard_envelope():
    r=advance_coarse_tick(side='BUY',current_price=.80,theoretical_price=.85,normalized_price=.80,increment=.05,maximum_debit=.84,executable_price=.85)
    assert r['price']==.80 and not r['advanced']
