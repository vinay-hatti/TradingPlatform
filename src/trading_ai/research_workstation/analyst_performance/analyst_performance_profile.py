from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class AnalystCalibrationProfile:
    case_count: int
    average_predicted_probability: float
    realized_success_rate: float
    calibration_error: float
    brier_score: float
    confidence_drift: float
    calibration_status: str


@dataclass(frozen=True)
class AnalystAttributionProfile:
    dimension: str
    key: str
    case_count: int
    win_count: int
    loss_count: int
    win_rate: float
    average_institutional_score: float
    average_evidence_quality: float


@dataclass(frozen=True)
class AnalystGovernanceProfile:
    case_count: int
    warning_count: int
    rejection_count: int
    governance_failure_rate: float
    missing_evidence_count: int
    incomplete_case_count: int
    excessive_confidence_count: int
    findings: tuple[str, ...]


@dataclass(frozen=True)
class AnalystScorecardProfile:
    analyst_id: str
    case_count: int
    win_count: int
    loss_count: int
    neutral_count: int
    win_rate: float
    average_institutional_score: float
    average_evidence_quality: float
    average_case_completeness: float
    calibration: AnalystCalibrationProfile
    governance: AnalystGovernanceProfile
    strategy_attribution: tuple[AnalystAttributionProfile, ...]
    sector_attribution: tuple[AnalystAttributionProfile, ...]
    composite_score: float
    rating: str
    strengths: tuple[str, ...]
    improvement_areas: tuple[str, ...]
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AnalystPerformanceReportProfile:
    report_id: str
    generated_at: datetime
    analyst_count: int
    total_case_count: int
    scorecards: tuple[AnalystScorecardProfile, ...]
    governance_status: str
    warnings: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)
