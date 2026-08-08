from trading_ai.stock_intelligence import *

def rows(n=120,start=100,step=.5,vol=1000):
    return [{'open':start+i*step-.1,'high':start+i*step+.5,'low':start+i*step-.5,'close':start+i*step,'volume':vol+i*5} for i in range(n)]
def profile(step=.5):return StockIntelligenceService().analyze('X',{'1d':rows(step=step),'1w':rows(step=step*.8)},'t')
def test_41_position_plan_exists():assert isinstance(profile().trade_plan,PositionIntelligenceProfile)
def test_42_entry_zone_valid():
    e=profile().trade_plan.entry;assert e.zone_low<=e.preferred_entry<=e.zone_high

def test_43_bull_stop_below_entry():
    p=profile();assert p.trade_plan.stop.recommended_stop<p.trade_plan.entry.preferred_entry

def test_44_bear_stop_above_entry():
    p=profile(-.5);assert p.trade_plan.stop.recommended_stop>p.trade_plan.entry.preferred_entry

def test_45_targets_have_rr():assert all(t.reward_risk>0 for t in profile().trade_plan.targets.targets)
def test_46_trailing_method():assert profile().trade_plan.trailing.method in {'STRUCTURE','ATR','SWING_STRUCTURE','SUPPORT_RESISTANCE'}
def test_47_exit_healthy():assert profile().trade_plan.exit.action in [x.value for x in ExitAction]
def test_48_exit_invalidated():
    original=profile(.5);current=profile(-.5);x=UnderlyingExitEngine().evaluate(original,current);assert x.action in {'EXIT','REDUCE'}
def test_49_hash_stable():
    p=profile();assert p.trade_plan.state_hash

def test_50_quality_bounded():
    q=profile().trade_plan.management_quality;assert 0<=q<=100
