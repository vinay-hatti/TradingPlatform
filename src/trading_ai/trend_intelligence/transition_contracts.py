from __future__ import annotations
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any

@dataclass(frozen=True)
class TrendTransitionSnapshot:
    symbol: str
    as_of_date: str
    snapshot_timestamp: datetime
    transition_state: str
    transition_direction: str
    breakout_state: str
    channel_position_pct: float
    breakout_distance_pct: float
    momentum_acceleration_score: float
    volatility_state: str
    volatility_percentile: float
    compression_score: float
    reversal_risk_score: float
    exhaustion_risk_score: float
    confirmation_score: float
    signal_adjustment: dict[str, float]
    status: str = 'READY'
    calculation_version: str = 'trend_transition.v1'
    warnings: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    def to_dict(self):
        p=asdict(self); p['snapshot_timestamp']=self.snapshot_timestamp.isoformat(); return p
