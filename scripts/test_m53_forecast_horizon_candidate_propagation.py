from dataclasses import fields
from trading_ai.daily.models import DailyCandidate
from trading_ai.daily.trade_candidate import LiveTradeCandidate

REQUIRED = {
    "forecast_requested_horizon_days",
    "forecast_resolved_horizon_days",
    "forecast_horizon_distance_days",
    "forecast_horizon_resolution",
}

for cls in (DailyCandidate, LiveTradeCandidate):
    names = {f.name for f in fields(cls)}
    missing = REQUIRED - names
    assert not missing, f"{cls.__name__} missing {sorted(missing)}"

candidate = DailyCandidate(
    symbol="SPX", signal="CALL", strategy="LONG_CALL", close=7411.98,
    score=80.0, call_score=80.0, put_score=0.0, market_regime="BULL_TREND",
    strike=7600.0, expiry="2026-09-29", option_price=1.0, delta=.3962,
    gamma=.01, theta=-.02, vega=.1, rho=.01, volatility=.2, dte=63,
    final_score=80.0, forecast_requested_horizon_days=63,
    forecast_resolved_horizon_days=20, forecast_horizon_distance_days=43,
    forecast_horizon_resolution="NEAREST_AVAILABLE",
)
assert candidate.forecast_resolved_horizon_days == 20
print("Milestone 53 forecast horizon candidate propagation assertions passed.")
