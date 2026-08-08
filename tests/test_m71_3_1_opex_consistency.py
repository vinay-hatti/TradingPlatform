from datetime import date
from types import SimpleNamespace
from trading_ai.opex_intelligence.service import OpexIntelligenceService


def svc():
    return OpexIntelligenceService(lambda: None)


def test_probability_coherence_caps_breakout_by_acceptance_and_preserves_total():
    s=svc()
    scenarios=[
        {'name':'PIN_RANGE','probability':15.0},
        {'name':'BULLISH_BREAKOUT','probability':54.0},
        {'name':'BEARISH_BREAKDOWN','probability':17.0},
        {'name':'VOLATILITY_SHOCK','probability':14.0},
    ]
    levels=[
        {'label':'RESISTANCE','touch_probability':37.3,'acceptance_probability':5.45},
        {'label':'SUPPORT','touch_probability':87.8,'acceptance_probability':39.16},
    ]
    out=s._coherent_scenarios(scenarios,levels,8000,7750)
    probs={x['name']:x['probability'] for x in out}
    assert probs['BULLISH_BREAKOUT'] <= 5.45 + 0.01
    assert probs['BEARISH_BREAKDOWN'] <= 39.16 + 0.01
    assert abs(sum(probs.values())-100) < .05


def test_path_ladder_is_monotonic():
    s=svc()
    dominant={'name':'BULLISH_BREAKOUT','probability':20.0}
    levels=[
        {'label':'GAMMA_FLIP','price':7823.35,'side':'UPSIDE','touch_probability':88.6},
        {'label':'RESISTANCE','price':8000,'side':'UPSIDE','touch_probability':37.3},
    ]
    stages=[
        {'stage':1,'low':7980,'high':8020,'conditional_probability':20},
        {'stage':2,'low':8020,'high':8070,'conditional_probability':14},
        {'stage':3,'low':8070,'high':8130,'conditional_probability':8},
    ]
    rows=s._path_ladder(7757.64,dominant,levels,stages)
    ps=[x['probability'] for x in rows]
    assert all(a >= b for a,b in zip(ps,ps[1:]))
    assert rows[0]['label']=='SPOT'
    assert any(x['label']=='GAMMA_FLIP' for x in rows)


def test_daily_path_uses_quantiles_and_macro_state_only_for_material_events():
    s=svc()
    event=SimpleNamespace(event_date='2026-08-12')
    rows=s._expected_daily_path(
        '2026-08-10', date(2026,8,14), 7757.64,
        {'name':'PIN_RANGE','probability':45},
        [{'stage':1,'low':7975,'high':8025,'conditional_probability':45}],
        [],
        [{'event':event,'type':'CPI','weight':1.0,'weighted_move_pct':0.6}],
        {'score':57.5,'ticker':'ESU6'},
        {'rv20':8.1,'score':64.8},
    )
    by={x['date']:x for x in rows}
    assert by['2026-08-12']['state']=='MACRO_EVENT'
    assert by['2026-08-10']['state']!='MACRO_EVENT'
    for r in rows:
        assert r['p25'] <= r['median'] <= r['p75']


def test_magnet_heatmap_separates_probability_and_attraction():
    s=svc()
    mags=[(7975,20,None),(8000,60,None),(8025,20,None)]
    surface={'density':[{'price':7975,'probability_mass':5},{'price':8000,'probability_mass':8},{'price':8025,'probability_mass':5}]}
    rows=s._magnet_zone_heatmap(8000,mags,surface,7757.64,25)
    assert all('attraction_score' in x for x in rows)
    assert all(0 <= x['attraction_score'] <= 100 for x in rows)


def test_cross_opex_exposes_decision_and_terminal_base_zones():
    s=svc()
    f={
        'symbol':'SPX','expiration':'2026-08-21','dte':13,
        'magnet':{'price':8000,'zone':{'probability':4}},
        'model_calibrated_ranges':{'50':{'low':7700,'high':8120},'68':{'low':7600,'high':8270}},
        'ranges':{'68':{'low':7500,'high':8300}},
        'actionable_range':{'low':7980,'high':8070},
        'conditional_distributions':[{'name':'BASE_EVENT_OUTCOME','range':{'low':7708,'high':8117}}],
        'migration':{'gamma_flip':{'forecast':7823},'call_wall':{'forecast':8000},'put_wall':{'forecast':7750}},
        'dealer':{'pressure_score':-20},'confidence':{'overall':75},
        'scenarios':[{'name':'PIN_RANGE','probability':50},{'name':'BULLISH_BREAKOUT','probability':10},{'name':'BEARISH_BREAKDOWN','probability':15},{'name':'VOLATILITY_SHOCK','probability':25}],
    }
    node=s._cross_opex([f])[0]['nodes'][0]
    assert node['current_decision_zone']=={'low':7980,'high':8070}
    assert node['terminal_base_zone']=={'low':7708,'high':8117}


def test_actionable_is_assigned_before_summary_reads_bounds():
    from pathlib import Path
    service = Path(__file__).resolve().parents[1] / 'src/trading_ai/opex_intelligence/service.py'
    source = service.read_text()
    assign_pos = source.find("staged,actionable=self._realistic_staged_objectives")
    read_pos = source.find("alo=actionable['low']; ahi=actionable['high']")
    assert assign_pos >= 0
    assert read_pos > assign_pos
