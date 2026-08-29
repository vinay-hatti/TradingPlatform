from datetime import datetime, timezone
from trading_ai.market_overview.contracts import MarketOverviewSnapshot
from trading_ai.market_overview.integration import market_score_adjustment

snap=MarketOverviewSnapshot(datetime.now(timezone.utc),'2026-07-24','MODERATELY_BULLISH','SELECTIVE_DIRECTIONAL_SPREADS',70,72,65,68,67,64,85,'UPTREND','NORMAL','HEALTHY_BROAD','NORMAL','NORMAL','LOW')
p=snap.to_dict()
assert p['market_bias']=='MODERATELY_BULLISH'
call,reasons=market_score_adjustment({'market_bias':'MODERATELY_BULLISH','trend_score':72,'breadth_score':68,'volatility_regime':'EXPANDING','regime_transition_risk':'LOW'},'CALL')
put,_=market_score_adjustment({'market_bias':'MODERATELY_BULLISH','trend_score':72,'breadth_score':68,'volatility_regime':'EXPANDING','regime_transition_risk':'LOW'},'PUT')
assert call>0 and put<call and reasons
assert abs(call)<=8 and abs(put)<=8
print('Milestone 45 market overview contract assertions passed.')
