from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class InstitutionalTrendSnapshot:
    symbol: str
    as_of_date: str
    snapshot_timestamp: datetime
    participation_score: float
    participation_grade: str
    participation_confidence: float
    institutional_conviction_score: float
    relative_volume_20d: float
    volume_trend_score: float
    volume_thrust_score: float
    price_volume_confirmation_score: float
    accumulation_distribution_score: float
    distribution_risk_score: float
    leadership_score: float
    leadership_grade: str
    market_relative_strength_20d: float
    market_relative_strength_60d: float
    leadership_persistence_score: float
    breadth_confirmation_score: float
    cross_asset_confirmation_score: float
    trend_quality_score: float
    deterioration_risk_score: float
    participation_state: str
    leadership_state: str
    deterioration_state: str
    status: str = "READY"
    calculation_version: str = "institutional_trend.v1"
    warnings: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["snapshot_timestamp"] = self.snapshot_timestamp.isoformat()
        return value
