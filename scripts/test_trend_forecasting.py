import numpy as np, pandas as pd
from trading_ai.trend_intelligence.forecast_engine import TrendForecastEngine
idx=pd.date_range("2026-01-01",periods=180,freq="B")
prices=pd.DataFrame({"close":100*np.cumprod(1+np.linspace(0.0002,0.0012,len(idx)))},index=idx)
engine=TrendForecastEngine(); snap=engine.calculate("TEST",prices,10)
assert snap.status=="READY" and snap.horizon_days==10
assert 0<=snap.continuation_probability<=100 and 0<=snap.reversal_probability<=100
assert abs(snap.signal_adjustment["CALL"])<=1.5 and snap.signal_adjustment["PUT"]==-snap.signal_adjustment["CALL"]
print("All Trend Forecasting assertions passed.")
