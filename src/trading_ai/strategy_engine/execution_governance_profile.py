from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ExecutionPopulationProfile:
    name: str = "UNAVAILABLE"
    observation_count: int = 0
    metric_count: int = 0
    segment_count: int = 0
    valid: bool = False
    warnings: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ExecutionMetricDriftProfile:
    metric_name: str = "UNKNOWN"
    baseline_observation_count: int = 0
    current_observation_count: int = 0
    baseline_mean: float = 0.0
    current_mean: float = 0.0
    absolute_change: float = 0.0
    relative_change: float = 0.0
    baseline_standard_deviation: float = 0.0
    current_standard_deviation: float = 0.0
    standardized_shift: float = 0.0
    population_stability_index: float = 0.0
    drift_score: float = 100.0
    drift_grade: str = "N/A"
    drift_severity: str = "UNKNOWN"
    deteriorated: bool = False
    allowed: bool = True
    valid: bool = False
    warnings: tuple[str, ...] = ()
    rejection_reasons: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ExecutionSegmentDriftProfile:
    segment_type: str = "UNKNOWN"
    segment_name: str = "UNKNOWN"
    baseline_observation_count: int = 0
    current_observation_count: int = 0
    metric_count: int = 0
    aggregate_psi: float = 0.0
    maximum_psi: float = 0.0
    drift_score: float = 100.0
    drift_grade: str = "N/A"
    drift_severity: str = "UNKNOWN"
    allowed: bool = True
    valid: bool = False
    metric_profiles: tuple[ExecutionMetricDriftProfile, ...] = ()
    warnings: tuple[str, ...] = ()
    rejection_reasons: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ExecutionGovernanceProfile:
    valid: bool = False
    allowed: bool = True
    baseline_name: str = "UNAVAILABLE"
    current_name: str = "UNAVAILABLE"
    baseline_observation_count: int = 0
    current_observation_count: int = 0
    metric_count: int = 0
    segment_count: int = 0
    aggregate_psi: float = 0.0
    maximum_metric_psi: float = 0.0
    deteriorated_metric_count: int = 0
    governance_score: float = 0.0
    governance_grade: str = "N/A"
    drift_severity: str = "UNKNOWN"
    recommendation: str = "INSUFFICIENT_DATA"
    baseline_profile: ExecutionPopulationProfile | None = None
    current_profile: ExecutionPopulationProfile | None = None
    metric_profiles: tuple[ExecutionMetricDriftProfile, ...] = ()
    segment_profiles: tuple[ExecutionSegmentDriftProfile, ...] = ()
    warnings: tuple[str, ...] = ()
    rejection_reasons: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)
