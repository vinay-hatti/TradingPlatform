from datetime import date, datetime, timezone
from types import SimpleNamespace
from trading_ai.opex_intelligence.service import OpexIntelligenceService,is_monthly_opex

def ns(**kw): return SimpleNamespace(**kw)

def test_monthly_opex_classifier():
    assert is_monthly_opex(date(2026,9,18))
    assert not is_monthly_opex(date(2026,9,11))

def test_forecast_has_ranges_scenarios_flows_and_migrations():
    svc=OpexIntelligenceService(None)
    snap=ns(symbol='SPX',as_of_date=date(2026,8,7),spot_price=6400.,atm_iv=.18,bull_probability=58.,bear_probability=42.,range_probability=62.,breakout_probability=55.,breakdown_probability=35.,volatility_expansion_probability=40.,quote_coverage_pct=99.,confidence_score=88.,gamma_regime='POSITIVE_GAMMA',gamma_flip=6325.,primary_call_wall=6450.,primary_put_wall=6300.)
    prev=ns(gamma_flip=6315.,primary_call_wall=6425.,primary_put_wall=6275.)
    ep=ns(expiry=date(2026,8,21),dte=14,atm_implied_volatility=.18,expected_move=115.,liquidity_score=90.,net_gamma_exposure=1e9,net_delta_exposure=2e8,net_vanna_exposure=4e7,net_charm_exposure=2e7)
    strikes=[ns(strike=p,pin_score=70 if p==6375 else 30,liquidity_score=90,call_open_interest=50000 if p>=6400 else 10000,put_open_interest=50000 if p<=6300 else 10000,net_gamma_exposure=1e8 if p>=6375 else -8e7) for p in (6250,6300,6350,6375,6400,6450,6500)]
    f=svc._forecast(snap,prev,ep,None,strikes,{'score':62.,'direction':'BULLISH','rv20':16.},[],datetime.now(timezone.utc))
    assert f['ranges']['90']['low'] < f['ranges']['68']['low'] < f['ranges']['50']['low'] < f['ranges']['50']['high'] < f['ranges']['68']['high'] < f['ranges']['90']['high']
    assert len(f['scenarios'])==4 and round(sum(x['probability'] for x in f['scenarios']),1)==100.0
    assert len(f['daily_flows'])==15
    assert f['migration']['gamma_flip']['forecast'] is not None
    assert f['magnet']['candidates']
    assert 'modeled range' in f['summary']
