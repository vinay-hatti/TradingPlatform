from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class EnsembleComponentProfile:
    name: str
    strategy: str
    direction: str
    score: float
    confidence_score: float
    weight: float
    weighted_score: float
    available: bool
    allowed: bool
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class EnsembleStrategyProfile:
    symbol: str
    strategy: str
    direction: str
    ensemble_score: float
    meta_confidence_score: float
    consensus_ratio: float
    score_dispersion: float
    component_count: int
    allowed_component_count: int
    allowed: bool
    grade: str
    severity: str
    recommendation: str
    components: tuple[EnsembleComponentProfile, ...] = ()
    warnings: tuple[str, ...] = ()
    rejection_reasons: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class EnsembleDecisionProfile:
    symbol: str
    valid: bool
    allowed: bool
    selected_strategy: str | None
    selected_direction: str | None
    ensemble_score: float
    meta_confidence_score: float
    consensus_ratio: float
    grade: str
    severity: str
    recommendation: str
    strategies: tuple[EnsembleStrategyProfile, ...] = ()
    warnings: tuple[str, ...] = ()
    rejection_reasons: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)
