from dataclasses import dataclass, field


@dataclass
class CalibrationBin:
    bin_index: int
    lower_bound: float
    upper_bound: float
    observation_count: int
    mean_predicted_probability: float
    observed_frequency: float
    calibration_error: float


@dataclass
class CalibrationModel:
    method: str
    fitted: bool
    parameters: dict = field(default_factory=dict)
    x_thresholds: list[float] = field(default_factory=list)
    y_values: list[float] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)


@dataclass
class ProbabilityCalibrationProfile:
    model_id: str
    symbol: str
    strategy: str
    segment: str

    selected_method: str
    preferred_method: str
    observation_count: int
    training_count: int
    validation_count: int
    positive_count: int
    negative_count: int
    base_rate: float

    raw_brier_score: float
    calibrated_brier_score: float
    brier_improvement: float
    raw_log_loss: float
    calibrated_log_loss: float
    log_loss_improvement: float

    raw_ece: float
    calibrated_ece: float
    raw_mce: float
    calibrated_mce: float

    calibration_intercept: float | None
    calibration_slope: float | None
    sharpness: float
    discrimination_auc: float | None

    calibration_score: float
    calibration_grade: str
    calibration_severity: str
    allowed: bool
    valid: bool

    model: CalibrationModel
    raw_reliability_bins: list[CalibrationBin] = field(default_factory=list)
    calibrated_reliability_bins: list[CalibrationBin] = field(default_factory=list)
    candidate_metrics: dict = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    rejection_reasons: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)

    @property
    def improvement_accepted(self) -> bool:
        return self.selected_method != "IDENTITY"
