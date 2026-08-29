from __future__ import annotations
import numpy as np
import pandas as pd
from trading_ai.trend_intelligence.institutional_engine import InstitutionalTrendEngine

idx = pd.bdate_range("2025-01-01", periods=180)
close = 100 * np.cumprod(1 + np.linspace(0.0002, 0.0015, len(idx)))
volume = np.linspace(1_000_000, 2_400_000, len(idx))
prices = pd.DataFrame({"close": close, "volume": volume}, index=idx)
benchmark = pd.DataFrame({"close": 100 * np.cumprod(np.repeat(1.0003, len(idx))), "volume": volume}, index=idx)
snapshot = InstitutionalTrendEngine().calculate("TEST", prices, benchmark)
payload = snapshot.to_dict()
assert payload["symbol"] == "TEST"
for key in ["participation_score", "leadership_score", "trend_quality_score", "deterioration_risk_score"]:
    assert 0.0 <= payload[key] <= 100.0, (key, payload[key])
assert payload["participation_grade"] in {"A", "B", "C", "D", "F"}
assert payload["metadata"]["institutional_identity_claimed"] is False
print("All Institutional Trend Intelligence assertions passed.")
