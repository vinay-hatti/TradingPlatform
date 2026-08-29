from dataclasses import fields
from trading_ai.daily.models import DailyCandidate
from trading_ai.daily.trade_candidate import LiveTradeCandidate

def main():
    required={"base_trend_score_adjustment","transition_score_adjustment","combined_trend_score_adjustment","transition_state","breakout_state","reversal_risk_score","exhaustion_risk_score"}
    assert required <= {f.name for f in fields(DailyCandidate)}
    assert required <= {f.name for f in fields(LiveTradeCandidate)}
    print("All Trend Intelligence Phase 2 reporting contract assertions passed.")
if __name__=="__main__": main()
