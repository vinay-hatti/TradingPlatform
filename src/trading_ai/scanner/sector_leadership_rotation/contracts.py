from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from enum import Enum
from typing import Any


class SectorLeadershipGovernanceStatus(str, Enum):
    READY = "READY"
    REVIEW = "REVIEW"
    EXCLUDED = "EXCLUDED"


@dataclass(frozen=True)
class SectorRankProfile:
    symbol: str
    group: str
    classification: str
    return_5d: float | None
    return_21d: float | None
    relative_strength_21d: float | None
    trend_direction: str
    trend_strength: float | None
    liquidity_regime: str
    momentum_score: float
    rank: int
    percentile: float
    is_leader: bool
    is_laggard: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class SectorLeadershipProfile:
    as_of_date: date
    benchmark_symbol: str
    sector_count: int
    governed_sector_count: int

    advancing_sector_count: int
    declining_sector_count: int
    positive_relative_strength_count: int
    uptrend_sector_count: int

    breadth_score: float
    offensive_leadership_score: float
    defensive_leadership_score: float
    leadership_spread: float

    rotation_state: str
    leadership_state: str
    confidence: float

    leaders: tuple[str, ...]
    laggards: tuple[str, ...]
    rankings: tuple[SectorRankProfile, ...]

    governance_status: SectorLeadershipGovernanceStatus
    governance_reasons: tuple[str, ...]

    feature_version: str = "m35.phase5.step3.v1"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class SectorLeadershipRunProfile:
    as_of_date: date
    generated_at: datetime
    input_path: str
    output_path: str
    records_read: int
    sectors_available: int
    sectors_missing: int
    rotation_state: str
    leadership_state: str
    confidence: float
    governance_status: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
