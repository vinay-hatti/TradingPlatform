from dataclasses import dataclass, field

@dataclass
class CalibrationWindowMetrics:
    observation_count: int
    positive_count: int
    negative_count: int
    base_rate: float
    brier_score: float
    log_loss: float
    expected_calibration_error: float
    maximum_calibration_error: float
    mean_probability: float

@dataclass
class ProbabilityCalibrationDriftProfile:
    model_version: str
    segment_key: str
    reference_metrics: CalibrationWindowMetrics
    recent_metrics: CalibrationWindowMetrics
    brier_change: float
    log_loss_change: float
    ece_change: float
    base_rate_shift: float
    mean_probability_shift: float
    probability_psi: float
    drift_score: float
    drift_grade: str
    drift_severity: str
    allowed: bool
    valid: bool
    warnings: list[str] = field(default_factory=list)
    rejection_reasons: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)
