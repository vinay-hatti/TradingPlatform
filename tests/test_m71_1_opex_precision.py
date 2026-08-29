from datetime import date, datetime, timedelta, timezone
from math import exp, log, sqrt
from statistics import NormalDist
from types import SimpleNamespace
from trading_ai.opex_intelligence.service import OpexIntelligenceService

N=NormalDist()
def ns(**kw): return SimpleNamespace(**kw)
def call_price(s,k,t,iv,r=.04):
    d1=(log(s/k)+(r+.5*iv*iv)*t)/(iv*sqrt(t)); d2=d1-iv*sqrt(t)
    return s*N.cdf(d1)-k*exp(-r*t)*N.cdf(d2)

def test_surface_distribution_builds_ordered_risk_neutral_ranges():
    svc=OpexIntelligenceService(None); spot=6400.; t=30/365
    rows=[]
    for k in range(5600,7201,50):
        iv=.19 + .000000035*(k-6400)**2 + (.015 if k<6200 else 0)
        mid=call_price(spot,k,t,iv)
        rows.append(ns(strike=float(k),mid=mid,bid=max(.01,mid-.5),ask=mid+.5,spread_pct=.01,implied_volatility=iv,option_type='CALL'))
    out=svc._surface_distribution(rows,spot)
    assert out['status']=='READY'
    assert out['ranges']['90']['low'] <= out['ranges']['68']['low'] <= out['ranges']['50']['low']
    assert out['ranges']['50']['high'] <= out['ranges']['68']['high'] <= out['ranges']['90']['high']
    assert out['quality']>40
    assert out['density']

def test_precision_forecast_exposes_actionable_path_and_magnet_zone():
    svc=OpexIntelligenceService(None); today=date(2026,8,7); spot=6400.; expiry=date(2026,9,18); t=42/365
    snap=ns(symbol='SPX',as_of_date=today,spot_price=spot,atm_iv=.18,bull_probability=58.,bear_probability=42.,range_probability=62.,breakout_probability=55.,breakdown_probability=35.,volatility_expansion_probability=40.,quote_coverage_pct=99.,confidence_score=88.,gamma_regime='POSITIVE_GAMMA',gamma_flip=6325.,primary_call_wall=6500.,primary_put_wall=6250.)
    prev=ns(gamma_flip=6310.,primary_call_wall=6475.,primary_put_wall=6225.)
    ep=ns(expiry=expiry,dte=42,atm_implied_volatility=.18,expected_move=240.,liquidity_score=93.,net_gamma_exposure=1e9,net_delta_exposure=2e8,net_vanna_exposure=4e7,net_charm_exposure=2e7)
    strikes=[];surface=[]
    for k in range(5800,7001,50):
        strikes.append(ns(strike=float(k),pin_score=80 if k==6400 else 35,liquidity_score=92,call_open_interest=70000 if k>=6450 else 18000,put_open_interest=65000 if k<=6300 else 16000,call_volume=8000,put_volume=7000,net_gamma_exposure=1e8 if 6300<=k<=6500 else -5e7))
        iv=.18+.00000003*(k-6400)**2;mid=call_price(spot,k,t,iv);surface.append(ns(strike=float(k),mid=mid,bid=max(.01,mid-.5),ask=mid+.5,spread_pct=.01,implied_volatility=iv,option_type='CALL'))
    f=svc._forecast(snap,prev,ep,None,strikes,{'score':62.,'direction':'BULLISH','rv20':16.,'momentum20':3.},[],datetime.now(timezone.utc),surface=surface,prices=[],prior_strikes=[],tactical_expiries=[],cross_index={'score':82.,'state':'BULLISH_CONFIRMED'},overview=None)
    assert f['surface_distribution']['status']=='READY'
    assert f['model_calibrated_ranges']['68']['low'] < f['model_calibrated_ranges']['68']['high']
    assert f['actionable_range']['low'] < f['actionable_range']['high']
    assert f['actionable_range']['conditional'] is True
    assert f['magnet']['zone']['low'] < f['magnet']['zone']['high']
    assert 0 <= f['magnet']['zone']['probability'] <= 100
    assert f['magnet']['zone']['probability_method']=='RISK_NEUTRAL_SURFACE_MASS'
    assert f['magnet']['probability_semantics']=='NORMALIZED_STRIKE_ATTRACTION_WEIGHT_NOT_CALIBRATED'
    assert f['path_distribution']['levels']
    assert all(0 <= x['touch_probability'] <= 100 for x in f['path_distribution']['levels'])
    assert f['range_width_contributors'] and round(sum(f['range_width_contributors'].values()),0)==100
    assert f['dealer']['positioning_scope']=='TARGET_EXPIRATION'
    assert 'cross_index_confirmation' in f
    assert f['path_completeness']['status']=='COMPLETE'
    assert f['expected_daily_path'][-1]['date']==str(expiry)
    assert f['daily_flows'][-1]['date']==str(expiry)

def test_position_change_inference_is_explicit_not_fabricated():
    svc=OpexIntelligenceService(None)
    cur=[ns(call_open_interest=1200.,put_open_interest=1000.,call_volume=400.,put_volume=300.)]
    prior=[ns(call_open_interest=700.,put_open_interest=600.,call_volume=0.,put_volume=0.)]
    p=svc._position_change(cur,prior)
    assert p['state']=='LIKELY_OPENING'
    assert p['open_interest_change']>0
    assert p['method']=='OI_CHANGE_PLUS_INTRADAY_VOLUME_INFERENCE'
