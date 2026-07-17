from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ExecutionComparisonMetricProfile:
    metric: str = "UNKNOWN"
    champion_value: float = 0.0
    challenger_value: float = 0.0
    absolute_change: float = 0.0
    relative_change: float = 0.0
    improvement: float = 0.0
    favorable: bool = False
    weight: float = 0.0
    weighted_score: float = 0.0
    severity: str = "UNKNOWN"
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ExecutionChampionChallengerProfile:
    valid: bool = False
    allowed: bool = False
    route_type: str = "VENUE"
    champion_version: str = "UNAVAILABLE"
    challenger_version: str = "UNAVAILABLE"
    champion_route_name: str = "UNKNOWN"
    challenger_route_name: str = "UNKNOWN"
    champion_observation_count: int = 0
    challenger_observation_count: int = 0
    metric_comparisons: tuple[ExecutionComparisonMetricProfile, ...] = ()
    route_score_improvement: float = 0.0
    shortfall_improvement_bps: float = 0.0
    fill_ratio_change: float = 0.0
    latency_change_seconds: float = 0.0
    spread_change_bps: float = 0.0
    market_impact_change_bps: float = 0.0
    effective_spread_change_bps: float = 0.0
    champion_governance_score: float = 0.0
    challenger_governance_score: float = 0.0
    evaluation_score: float = 0.0
    confidence_score: float = 0.0
    evaluation_grade: str = "N/A"
    governance_severity: str = "UNKNOWN"
    recommendation: str = "HOLD_CHAMPION"
    promoted: bool = False
    warnings: tuple[str, ...] = ()
    rejection_reasons: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ExecutionChampionChallengerBatchProfile:
    valid: bool = False
    champion_version: str = "UNAVAILABLE"
    challenger_count: int = 0
    eligible_count: int = 0
    best_challenger_version: str = "UNAVAILABLE"
    best_evaluation_score: float = 0.0
    recommendation: str = "NO_ELIGIBLE_CHALLENGER"
    evaluations: tuple[ExecutionChampionChallengerProfile, ...] = ()
    warnings: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)
