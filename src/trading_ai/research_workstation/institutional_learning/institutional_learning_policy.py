from dataclasses import dataclass

@dataclass(frozen=True)
class InstitutionalLearningPolicy:
    minimum_cases: int = 2
    minimum_factor_occurrences: int = 2
    prior_alpha: float = 1.0
    prior_beta: float = 1.0
    high_confidence_threshold: float = 0.70
    low_confidence_threshold: float = 0.40
    maximum_adjustment: float = 0.15
    calibration_bins: int = 5
    def validate(self) -> None:
        if self.minimum_cases < 1 or self.minimum_factor_occurrences < 1: raise ValueError("minimum counts must be positive")
        if self.prior_alpha <= 0 or self.prior_beta <= 0: raise ValueError("beta priors must be positive")
        if not 0 <= self.low_confidence_threshold <= self.high_confidence_threshold <= 1: raise ValueError("invalid confidence thresholds")
        if not 0 <= self.maximum_adjustment <= 1: raise ValueError("maximum_adjustment must be between 0 and 1")
        if self.calibration_bins < 2: raise ValueError("calibration_bins must be at least 2")
