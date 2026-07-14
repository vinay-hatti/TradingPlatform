from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class WalkForwardCalibrationMetrics:
    observation_count: int = 0
    raw_brier_score: float = 0.0
    calibrated_brier_score: float = 0.0
    raw_log_loss: float = 0.0
    calibrated_log_loss: float = 0.0
    brier_improvement: float = 0.0
    log_loss_improvement: float = 0.0
    expected_calibration_error: float = 0.0
    maximum_calibration_error: float = 0.0
    segment_coverage: float = 0.0
    model_score: float = 0.0
    valid: bool = False
    warnings: list[str] = field(default_factory=list)
    rejection_reasons: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class WalkForwardCalibrationWindowResult:
    window_id: str
    selected_parameters: dict[str, Any] = field(default_factory=dict)
    validation_metrics: WalkForwardCalibrationMetrics = field(default_factory=WalkForwardCalibrationMetrics)
    test_metrics: WalkForwardCalibrationMetrics = field(default_factory=WalkForwardCalibrationMetrics)
    model_registry_id: str = "UNAVAILABLE"
    model_version: str = "UNAVAILABLE"
    model_segment_count: int = 0
    model_valid_segment_count: int = 0
    model_score_degradation: float = 0.0
    valid: bool = True
    allowed: bool = True
    warnings: list[str] = field(default_factory=list)
    rejection_reasons: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class WalkForwardProbabilityCalibrationProfile:
    window_count: int = 0
    completed_window_count: int = 0
    results: list[WalkForwardCalibrationWindowResult] = field(default_factory=list)
    average_oos_brier_improvement: float = 0.0
    average_oos_log_loss_improvement: float = 0.0
    average_oos_ece: float = 0.0
    worst_oos_mce: float = 0.0
    average_segment_coverage: float = 0.0
    average_model_score: float = 0.0
    model_stability_score: float = 0.0
    calibration_walk_forward_score: float = 0.0
    calibration_walk_forward_grade: str = "F"
    risk_severity: str = "UNKNOWN"
    allowed: bool = False
    valid: bool = False
    active_model_version: str = "UNAVAILABLE"
    warnings: list[str] = field(default_factory=list)
    rejection_reasons: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
