from trading_ai.stock_intelligence.profile import (
    StockIntelligenceProfile, TimeframeState, EntryProfile, StopProfile,
    TargetProfile, TargetLevel, TrailingProfile, ExitIntelligence,
    PositionIntelligenceProfile,
)
from trading_ai.trade_plan_certification import certify_stock_trade_plan, certify_option_trade_plan


def profile(direction='BULLISH', close=100.0):
    return StockIntelligenceProfile(
        'XYZ','2026-08-13T17:00:00+00:00',primary_timeframe='1d',direction=direction,
        timeframe_states={'1d':TimeframeState('1d',direction,'TRENDING',80,80,80,close,2)},
    )


def plan(stop=95, targets=(110,120,130), entry=(99,101)):
    return PositionIntelligenceProfile(
        entry=EntryProfile(zone_low=entry[0],zone_high=entry[1]),
        stop=StopProfile(recommended_stop=stop),
        targets=TargetProfile(targets=[TargetLevel(f'TARGET_{i+1}',x,70,2+i) for i,x in enumerate(targets)]),
        trailing=TrailingProfile(method='SWING_STRUCTURE'),
        exit=ExitIntelligence(reason='THESIS_HEALTHY'),structural_reward_risk=2,
    )


def test_bullish_targets_must_be_above_reference():
    c=certify_stock_trade_plan(profile(),plan(targets=(99,110,120)))
    assert c['status']=='FAIL'
    assert 'TPC-GEO-001' in c['failure_codes']


def test_bearish_targets_must_be_below_reference():
    c=certify_stock_trade_plan(profile('BEARISH'),plan(stop=105,targets=(101,95,90),entry=(99,101)))
    assert c['status']=='FAIL'
    assert 'TPC-GEO-002' in c['failure_codes']


def test_valid_bullish_plan_is_certified_with_ingested_reference():
    c=certify_stock_trade_plan(profile(),plan())
    assert c['status']=='PASS'
    assert c['publishable'] is True
    assert c['reference_market']['price']==100.0
    assert c['reference_market']['source']=='LATEST_UNDERLYING_INGESTION'
    assert c['version'].startswith('M75.2-ITPCE')


def test_diagonal_strategy_certification_requires_longer_long_leg():
    base=certify_stock_trade_plan(profile(),plan())
    good=certify_option_trade_plan(
        strategy='CALL_DIAGONAL',stock_certification=base,
        legs=[{'side':'BUY','option_symbol':'O:XYZ261016C00100000','expiry':'2026-10-16','strike':100},
              {'side':'SELL','option_symbol':'O:XYZ260911C00110000','expiry':'2026-09-11','strike':110}],
        checks={'risk_within_budget':True,'defined_risk':True},
        dynamic_management={'underlying_stop':95,'underlying_targets':[110,120],'trailing_policy':'SWING','volatility_exit_rule':'EXIT'},
    )
    assert good['status']=='PASS'
    bad=certify_option_trade_plan(
        strategy='CALL_DIAGONAL',stock_certification=base,
        legs=[{'side':'BUY','option_symbol':'O:XYZ260904C00100000','expiry':'2026-09-04','strike':100},
              {'side':'SELL','option_symbol':'O:XYZ260911C00110000','expiry':'2026-09-11','strike':110}],
        checks={'risk_within_budget':True,'defined_risk':True},
        dynamic_management={'underlying_stop':95,'underlying_targets':[110],'trailing_policy':'SWING','volatility_exit_rule':'EXIT'},
    )
    assert bad['status']=='FAIL'
    assert 'TPC-STR-031' in bad['failure_codes']
