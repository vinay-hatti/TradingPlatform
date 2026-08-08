from trading_ai.option_valuation_intelligence.events.policy import EventSyncPolicy

def test_daily_policy_is_six_months():
    p=EventSyncPolicy()
    assert p.horizon_months==6
    assert p.earnings_horizon=='6month'
