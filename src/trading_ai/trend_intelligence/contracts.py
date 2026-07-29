from __future__ import annotations
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any

@dataclass(frozen=True)
class TrendHorizon:
    name: str
    direction: str
    state: str
    score: float
    strength: float
    confidence: float
    slope_pct: float
    price_vs_anchor_pct: float
    persistence_pct: float
    lookback_days: int
    warnings: list[str] = field(default_factory=list)

@dataclass(frozen=True)
class TrendSnapshot:
    symbol: str
    as_of_date: str
    snapshot_timestamp: datetime
    short_term: TrendHorizon
    intermediate_term: TrendHorizon
    long_term: TrendHorizon
    alignment_score: float
    signal_alignment: dict[str, float]
    trend_quality_score: float
    trend_confidence: float
    trend_stage: str
    trend_age_days: int
    relative_strength_vs_spy: float
    relative_strength_vs_sector: float
    relative_strength_grade: str
    sector: str
    sector_etf: str
    market_alignment_score: float
    sector_alignment_score: float
    status: str = "READY"
    calculation_version: str = "trend.v1"
    warnings: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["snapshot_timestamp"] = self.snapshot_timestamp.isoformat()
        return payload
