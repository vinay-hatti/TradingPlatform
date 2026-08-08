from trading_ai.option_valuation_intelligence.events.outcomes import _pct


def test_pct_directional_move():
    assert round(_pct(105,100),6)==5.0
    assert round(_pct(95,100),6)==-5.0
    assert _pct(100,0) is None
