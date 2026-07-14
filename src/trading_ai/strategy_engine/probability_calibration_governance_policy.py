from dataclasses import dataclass
@dataclass
class ProbabilityCalibrationGovernancePolicy:
    minimum_evaluation_observations: int = 200
    minimum_brier_improvement: float = 0.002
    minimum_log_loss_improvement: float = 0.002
    maximum_ece_deterioration: float = 0.01
    minimum_challenger_score: float = 60.0
    require_challenger_allowed: bool = True
    reject_critical_drift: bool = True
    automatic_promotion_enabled: bool = False
    def validate(self):
        if self.minimum_evaluation_observations < 1: raise ValueError('minimum_evaluation_observations must be positive')
        return self
