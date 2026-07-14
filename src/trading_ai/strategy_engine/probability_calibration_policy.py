from dataclasses import dataclass


@dataclass(frozen=True)
class ProbabilityCalibrationPolicy:
    """Institutional controls for probability calibration and validation."""

    preferred_method: str = "AUTO"
    minimum_observations: int = 100
    minimum_positive_observations: int = 20
    minimum_negative_observations: int = 20
    validation_fraction: float = 0.25
    minimum_validation_observations: int = 40

    probability_floor: float = 1e-6
    probability_ceiling: float = 1.0 - 1e-6
    reliability_bin_count: int = 10

    maximum_iterations: int = 200
    convergence_tolerance: float = 1e-9
    l2_regularization: float = 1e-4

    brier_weight: float = 0.65
    log_loss_weight: float = 0.35
    minimum_relative_improvement: float = 0.005
    maximum_acceptable_ece: float = 0.08
    severe_ece_threshold: float = 0.15
    critical_ece_threshold: float = 0.25

    reject_critical_calibration: bool = True
    require_out_of_sample_improvement: bool = True

    def validate(self) -> None:
        method = self.preferred_method.upper()
        if method not in {"AUTO", "PLATT", "ISOTONIC", "IDENTITY"}:
            raise ValueError("preferred_method must be AUTO, PLATT, ISOTONIC, or IDENTITY")
        if self.minimum_observations < 20:
            raise ValueError("minimum_observations must be at least 20")
        if not 0.05 <= self.validation_fraction <= 0.50:
            raise ValueError("validation_fraction must be between 0.05 and 0.50")
        if self.reliability_bin_count < 3:
            raise ValueError("reliability_bin_count must be at least 3")
        if not 0.0 < self.probability_floor < self.probability_ceiling < 1.0:
            raise ValueError("probability bounds are invalid")
        if self.brier_weight < 0 or self.log_loss_weight < 0:
            raise ValueError("metric weights cannot be negative")
        if self.brier_weight + self.log_loss_weight <= 0:
            raise ValueError("at least one metric weight must be positive")
