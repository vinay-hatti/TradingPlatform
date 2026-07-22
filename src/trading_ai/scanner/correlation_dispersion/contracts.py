from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from enum import Enum
from typing import Any


class CorrelationDispersionGovernanceStatus(str, Enum):
    READY = "READY"
    REVIEW = "REVIEW"
    EXCLUDED = "EXCLUDED"


@dataclass(frozen=True)
class PairCorrelationProfile:
    left_symbol: str
    right_symbol: str
    observation_count: int
    correlation_21d: float | None
    correlation_63d: float | None
    correlation_change: float | None
    stability_score: float | None
    breakdown_detected: bool
    relationship_state: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class CorrelationDispersionProfile:
    as_of_date: date
    symbol_count: int
    governed_symbol_count: int
    pair_count: int

    average_correlation_21d: float | None
    average_absolute_correlation_21d: float | None
    median_correlation_21d: float | None
    correlation_stability_score: float | None
    correlation_breakdown_count: int
    correlation_breakdown_ratio: float

    cross_sectional_dispersion_1d: float | None
    cross_sectional_dispersion_5d: float | None
    cross_sectional_dispersion_21d: float | None
    dispersion_change: float | None

    diversification_score: float
    concentration_risk_score: float
    correlation_regime: str
    dispersion_regime: str
    market_structure_state: str
    confidence: float

    strongest_positive_pairs: tuple[str, ...]
    strongest_negative_pairs: tuple[str, ...]
    breakdown_pairs: tuple[str, ...]
    pair_profiles: tuple[PairCorrelationProfile, ...]

    governance_status: CorrelationDispersionGovernanceStatus
    governance_reasons: tuple[str, ...]

    feature_version: str = "m35.phase5.step4.v1"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class CorrelationDispersionRunProfile:
    as_of_date: date
    generated_at: datetime
    input_path: str
    output_path: str
    records_read: int
    symbols_available: int
    pair_count: int
    correlation_regime: str
    dispersion_regime: str
    market_structure_state: str
    confidence: float
    governance_status: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
