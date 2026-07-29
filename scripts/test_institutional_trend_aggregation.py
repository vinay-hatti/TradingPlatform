from trading_ai.trend_intelligence.institutional_aggregation import build_institutional_market_overview
rows = [
 {"participation_score":70,"leadership_score":68,"trend_quality_score":66,"deterioration_risk_score":30,"participation_state":"ACCUMULATION","leadership_state":"LEADER","deterioration_state":"STABLE"},
 {"participation_score":40,"leadership_score":45,"trend_quality_score":44,"deterioration_risk_score":61,"participation_state":"MIXED","leadership_state":"NEUTRAL","deterioration_state":"WATCH"},
]
p = build_institutional_market_overview(rows)
assert p["status"] == "READY"
assert p["symbol_count"] == 2
assert p["participation_breadth_pct"] == 50.0
assert p["deterioration_watch_pct"] == 50.0
print("All Institutional Trend aggregation assertions passed.")
