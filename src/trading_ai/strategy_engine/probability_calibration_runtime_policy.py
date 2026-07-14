from dataclasses import dataclass


@dataclass
class ProbabilityCalibrationRuntimePolicy:
    enabled: bool = True
    require_active_model: bool = False
    reject_unapproved_model: bool = False
    preserve_raw_probability: bool = True
    minimum_model_score: float = 0.0
    maximum_probability_adjustment: float = 0.35

    def validate(self):
        if not 0.0 <= self.minimum_model_score <= 100.0:
            raise ValueError("minimum_model_score must be between 0 and 100")
        if not 0.0 <= self.maximum_probability_adjustment <= 1.0:
            raise ValueError("maximum_probability_adjustment must be between 0 and 1")
        return self
