from dataclasses import dataclass, field
@dataclass
class CalibrationModelEvaluation:
    version: str
    brier_score: float
    log_loss: float
    expected_calibration_error: float
    calibration_score: float
    allowed: bool
@dataclass
class ProbabilityCalibrationGovernanceProfile:
    champion_version: str
    challenger_version: str
    champion: CalibrationModelEvaluation
    challenger: CalibrationModelEvaluation
    brier_improvement: float
    log_loss_improvement: float
    ece_change: float
    recommendation: str
    promotion_eligible: bool
    promotion_applied: bool
    confidence_score: float
    governance_grade: str
    governance_severity: str
    allowed: bool
    valid: bool
    drift_profile: object | None = None
    warnings: list[str] = field(default_factory=list)
    rejection_reasons: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)
