from trading_ai.option_valuation_intelligence.events.expected_moves import _weighted

def test_governed_weights():
    value,effective=_weighted((6.9,5.8,5.4),(0.55,0.30,0.15))
    assert round(value,3)==6.345
    assert round(sum(effective.values()),8)==1.0

def test_missing_component_renormalizes_not_zero_fills():
    value,effective=_weighted((6.0,4.0,None),(0.55,0.30,0.15))
    assert round(value,6)==round((6*0.55+4*0.30)/0.85,6)
    assert effective['forecast']==0.0
