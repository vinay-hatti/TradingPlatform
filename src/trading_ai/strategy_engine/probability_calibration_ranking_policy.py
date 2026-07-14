from dataclasses import dataclass


@dataclass
class ProbabilityCalibrationRankingPolicy:
    enabled: bool = True
    calibration_weight: float = 0.15
    maximum_ranking_adjustment: float = 10.0
    minimum_model_score: float = 0.0
    reject_critical_calibration: bool = False
    reject_unapproved_calibration: bool = False

    def validate(self):
        if not 0.0 <= self.calibration_weight <= 1.0:
            raise ValueError("calibration_weight must be between 0 and 1")
        if not 0.0 <= self.maximum_ranking_adjustment <= 100.0:
            raise ValueError("maximum_ranking_adjustment must be between 0 and 100")
        if not 0.0 <= self.minimum_model_score <= 100.0:
            raise ValueError("minimum_model_score must be between 0 and 100")
        return self
