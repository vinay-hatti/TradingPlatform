from types import SimpleNamespace
from trading_ai.daily.scanner import DailyScanner

class Repo:
    def scanner_context(self,*a,**k):
        return {"transition_context_status":"FRESH","transition_snapshot_date":"2026-07-28","transition_snapshot_age_days":0,"transition_state":"BULLISH_TRANSITION","transition_direction":"BULLISH","breakout_state":"CONFIRMED_BREAKOUT","channel_position_pct":99.0,"momentum_acceleration_score":88.0,"volatility_state":"EXPANSION","volatility_percentile":80.0,"reversal_risk_score":10.0,"exhaustion_risk_score":15.0,"transition_confirmation_score":92.0,"transition_score_adjustment":2.0,"transition_context_warning":""}

def main():
    s=object.__new__(DailyScanner); s.enable_trend_transition_intelligence=True; s.trend_transition_repository=Repo(); s.maximum_transition_snapshot_age_days=3; s.end="2026-07-28"; s.transition_intelligence_weight=1.0; s.maximum_transition_score_adjustment=2.0
    c=s._trend_transition_context(symbol="AAPL",signal="CALL")
    assert c["transition_context_status"]=="FRESH"
    assert c["transition_score_adjustment"]==2.0
    s.transition_intelligence_weight=10.0
    assert s._trend_transition_context(symbol="AAPL",signal="CALL")["transition_score_adjustment"]==2.0
    print("All Trend Intelligence Phase 2 scanner integration assertions passed.")
if __name__=="__main__": main()
