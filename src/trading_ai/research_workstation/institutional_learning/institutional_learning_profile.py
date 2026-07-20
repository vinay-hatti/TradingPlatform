from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

@dataclass(frozen=True)
class LearningFactorProfile:
    factor_type: str
    factor_key: str
    occurrences: int
    successes: int
    failures: int
    posterior_success_probability: float
    average_institutional_score: float
    confidence_adjustment: float
    recommendation: str
    metadata: dict[str, Any] = field(default_factory=dict)

@dataclass(frozen=True)
class LearningSummaryProfile:
    total_cases: int
    successful_cases: int
    failed_cases: int
    empirical_success_rate: float
    brier_score: float
    calibration_error: float
    recommended_global_adjustment: float
    strongest_positive_factors: tuple[str, ...]
    strongest_negative_factors: tuple[str, ...]

@dataclass(frozen=True)
class InstitutionalLearningProfile:
    report_id: str
    generated_at: datetime
    governance_status: str
    strategy_learning: tuple[LearningFactorProfile, ...]
    sector_learning: tuple[LearningFactorProfile, ...]
    outcome_learning: tuple[LearningFactorProfile, ...]
    tag_learning: tuple[LearningFactorProfile, ...]
    summary: LearningSummaryProfile
    recommendations: tuple[str, ...]
    warnings: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)
