from trading_ai.trend_intelligence.forecast_repository import TrendForecastRepository
class Result:
    def scalar_one_or_none(self): return {"symbol":"TEST","as_of_date":"2026-07-28","forecast_direction":"BULLISH","continuation_probability":70,"reversal_probability":30,"confidence_score":75,"confidence_grade":"B","expected_return_pct":2,"expected_volatility_pct":4,"persistence_days_estimate":12,"signal_adjustment":{"CALL":1.0,"PUT":-1.0}}
class Session:
    def __enter__(self): return self
    def __exit__(self,*a): pass
    def execute(self,*a,**k): return Result()
repo=TrendForecastRepository(session_factory=lambda:Session())
ctx=repo.scanner_context("TEST","CALL",reference_date="2026-07-28")
assert ctx["forecast_context_status"]=="FRESH" and ctx["forecast_score_adjustment"]==1.0
print("All Trend Forecast repository assertions passed.")
