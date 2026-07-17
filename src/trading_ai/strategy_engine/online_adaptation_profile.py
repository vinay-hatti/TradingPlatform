from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class StrategyWeightUpdateProfile:
    strategy: str
    valid: bool
    allowed: bool
    current_weight: float
    target_weight: float
    proposed_weight: float
    applied_weight: float
    absolute_change: float
    relative_change: float
    performance_score: float
    confidence_score: float
    stability_score: float
    update_score: float
    observation_count: int
    grade: str
    severity: str
    warnings: tuple[str, ...] = ()
    rejection_reasons: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class OnlineAdaptationProfile:
    valid: bool
    allowed: bool
    update_count: int
    applied_update_count: int
    total_absolute_change: float
    maximum_absolute_change: float
    concentration_before: float
    concentration_after: float
    effective_strategy_count_before: float
    effective_strategy_count_after: float
    adaptation_score: float
    grade: str
    severity: str
    recommendation: str
    updates: tuple[StrategyWeightUpdateProfile, ...] = ()
    warnings: tuple[str, ...] = ()
    rejection_reasons: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class LearningStateVersionProfile:
    version: str
    created_at: datetime
    status: str
    weights: dict[str, float]
    adaptation_score: float
    source_version: str | None = None
    actor: str = "system"
    reason: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class LearningStateRegistryProfile:
    valid: bool
    schema_version: str
    active_version: str | None
    champion_version: str | None
    challenger_version: str | None
    versions: tuple[LearningStateVersionProfile, ...]
    warnings: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class LearningStatePromotionProfile:
    valid: bool
    allowed: bool
    champion_version: str | None
    challenger_version: str | None
    champion_score: float
    challenger_score: float
    improvement: float
    promotion_score: float
    recommendation: str
    grade: str
    severity: str
    warnings: tuple[str, ...] = ()
    rejection_reasons: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)
