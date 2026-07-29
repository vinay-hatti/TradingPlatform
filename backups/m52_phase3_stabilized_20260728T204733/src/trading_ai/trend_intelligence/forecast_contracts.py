from __future__ import annotations
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any

@dataclass(frozen=True)
class TrendForecastSnapshot:
    symbol: str
    as_of_date: str
    snapshot_timestamp: datetime
    horizon_days: int
    continuation_probability: float
    reversal_probability: float
    bullish_probability: float
    bearish_probability: float
    expected_return_pct: float
    expected_volatility_pct: float
    confidence_score: float
    confidence_grade: str
    persistence_days_estimate: int
    forecast_direction: str
    regime_transition_probabilities: dict[str, float]
    signal_adjustment: dict[str, float]
    status: str = "READY"
    calculation_version: str = "trend_forecast.v1"
    warnings: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["snapshot_timestamp"] = self.snapshot_timestamp.isoformat()
        return payload
