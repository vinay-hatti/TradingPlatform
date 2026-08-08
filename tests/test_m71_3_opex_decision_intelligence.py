from types import SimpleNamespace
from trading_ai.opex_intelligence.service import OpexIntelligenceService


def svc():
    return OpexIntelligenceService(lambda: None)


def strikes():
    return [SimpleNamespace(strike=x) for x in (7700,7725,7750,7775,7800,7825,7850,7875,7900,7925,7950,7975,8000,8025,8050,8075,8100)]


def test_bullish_stages_use_realistic_zone_width_and_nonzero_actionable_range():
    s=svc()
    dominant={'name':'BULLISH_BREAKOUT','probability':54.1}
    ranges={'50':{'low':7675,'high':8150},'68':{'low':7559,'high':8327},'90':{'low':7283,'high':8760}}
    trend={'rv20':8.1,'score':64.8}
    analogs={'median_max_excursion_up_pct':1.8,'median_max_excursion_down_pct':-.2}
    stages, action=s._realistic_staged_objectives(dominant,7757.64,7750,8000,ranges,trend,strikes(),analogs,8000)
    assert len(stages)==3
    assert stages[0]['low'] < 8000 < stages[0]['high']
    assert stages[0]['high']-stages[0]['low'] >= 20
    assert action['high'] > action['low']
    assert action['low'] < 8000 < action['high']
    assert stages[1]['low'] >= stages[0]['high']


def test_magnet_heatmap_is_nested_and_zone_based():
    s=svc(); spot=7757.64; magnet=8000.; spacing=25.
    mags=[(7975,20,None),(8000,60,None),(8025,20,None),(8050,5,None)]
    surface={'density':[{'price':7975,'probability_mass':8},{'price':8000,'probability_mass':18},{'price':8025,'probability_mass':9},{'price':8050,'probability_mass':4}]}
    rows=s._magnet_zone_heatmap(magnet,mags,surface,spot,spacing)
    assert [x['band'] for x in rows]==['CORE','PRIMARY','EXTENDED']
    assert rows[0]['low'] < magnet < rows[0]['high']
    assert rows[0]['high']-rows[0]['low'] >= 20
    assert rows[0]['probability'] <= rows[1]['probability'] <= rows[2]['probability']


def test_scenario_evidence_exposes_signed_factor_ledger():
    s=svc()
    overview=SimpleNamespace(breadth_score=76.1,trend_score=64.0)
    ev=s._scenario_evidence(-71.8,{'score':64.8},overview,57.5,{'score':76.9},{'probability':3.9},{'quality':45},.9,-77.3)
    factors={x['factor']:x for x in ev['rows']}
    assert factors['DEALER_POSITIONING']['direction']=='BEARISH'
    assert factors['BREADTH']['direction']=='BULLISH'
    assert factors['FUTURES_CONFIRMATION']['direction']=='BULLISH'
    assert -100 <= ev['net_directional_score'] <= 100


def test_cross_opex_contains_transition_probability_matrix():
    s=svc()
    base={
      'symbol':'SPX','dte':10,'magnet':{'price':8000,'zone':{'probability':12}},'model_calibrated_ranges':{'68':{'low':7600,'high':8200}},'ranges':{'68':{'low':7600,'high':8200}},
      'actionable_range':{'low':7985,'high':8050},'migration':{'gamma_flip':{'forecast':7825},'call_wall':{'forecast':8000},'put_wall':{'forecast':7750}},'dealer':{'pressure_score':-20},'confidence':{'overall':75},
      'scenarios':[{'name':'PIN_RANGE','probability':20},{'name':'BULLISH_BREAKOUT','probability':50},{'name':'BEARISH_BREAKDOWN','probability':20},{'name':'VOLATILITY_SHOCK','probability':10}],
    }
    a=dict(base,expiration='2026-08-21')
    b=dict(base,expiration='2026-09-18',dte=38,magnet={'price':8050,'zone':{'probability':16}},dealer={'pressure_score':-5},scenarios=[{'name':'PIN_RANGE','probability':25},{'name':'BULLISH_BREAKOUT','probability':45},{'name':'BEARISH_BREAKDOWN','probability':18},{'name':'VOLATILITY_SHOCK','probability':12}])
    out=s._cross_opex([a,b])[0]
    matrix=out['transitions'][0]['transition_probability_matrix']
    assert len(matrix)==4
    for row in matrix:
        assert abs(sum(row['to_probabilities'].values())-100) < .05
