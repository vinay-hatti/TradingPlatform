from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from enum import Enum
from typing import Any


class CrossAssetIntelligenceGovernanceStatus(str, Enum):
    READY = "READY"
    REVIEW = "REVIEW"
    EXCLUDED = "EXCLUDED"


@dataclass(frozen=True)
class CrossAssetDecisionAdjustment:
    call_score_adjustment: float
    put_score_adjustment: float
    confidence_multiplier: float
    position_size_multiplier: float
    allow_new_risk: bool
    preferred_direction: str
    rationale: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class CrossAssetIntelligenceProfile:
    as_of_date: date

    intermarket_state: str
    intermarket_confidence: float

    sector_rotation_state: str
    sector_leadership_state: str
    sector_confidence: float
    sector_leaders: tuple[str, ...]
    sector_laggards: tuple[str, ...]

    correlation_regime: str
    dispersion_regime: str
    market_structure_state: str
    structure_confidence: float

    composite_risk_on_score: float
    composite_risk_off_score: float
    composite_confidence: float

    macro_regime: str
    tactical_bias: str
    opportunity_regime: str
    systemic_risk_level: str

    decision_adjustment: CrossAssetDecisionAdjustment

    source_governance: dict[str, str]
    governance_status: CrossAssetIntelligenceGovernanceStatus
    governance_reasons: tuple[str, ...]

    feature_version: str = "m35.phase5.step5.v1"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class CrossAssetIntelligenceRunProfile:
    as_of_date: date
    generated_at: datetime
    intermarket_input_path: str
    sector_input_path: str
    correlation_input_path: str
    output_path: str
    macro_regime: str
    tactical_bias: str
    opportunity_regime: str
    systemic_risk_level: str
    composite_confidence: float
    governance_status: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
