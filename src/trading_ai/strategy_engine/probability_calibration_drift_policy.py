from dataclasses import dataclass

@dataclass
class ProbabilityCalibrationDriftPolicy:
    minimum_recent_observations: int = 100
    reliability_bins: int = 10
    probability_bins: int = 10
    probability_floor: float = 1e-6
    probability_ceiling: float = 1.0 - 1e-6
    warning_brier_increase: float = 0.02
    severe_brier_increase: float = 0.05
    critical_brier_increase: float = 0.10
    warning_ece_increase: float = 0.03
    severe_ece_increase: float = 0.07
    critical_ece_increase: float = 0.12
    warning_psi: float = 0.10
    severe_psi: float = 0.20
    critical_psi: float = 0.35
    warning_base_rate_shift: float = 0.05
    severe_base_rate_shift: float = 0.10
    critical_base_rate_shift: float = 0.20
    reject_critical_drift: bool = True

    def validate(self):
        if self.minimum_recent_observations < 1: raise ValueError('minimum_recent_observations must be positive')
        if self.reliability_bins < 2 or self.probability_bins < 2: raise ValueError('bin counts must be >= 2')
        if not 0 < self.probability_floor < self.probability_ceiling < 1: raise ValueError('invalid probability bounds')
        return self
