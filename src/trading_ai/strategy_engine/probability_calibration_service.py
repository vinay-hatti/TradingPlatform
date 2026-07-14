from trading_ai.strategy_engine.probability_calibration_engine import (
    ProbabilityCalibrationEngine,
)
from trading_ai.strategy_engine.probability_calibration_policy import (
    ProbabilityCalibrationPolicy,
)


class ProbabilityCalibrationService:
    def __init__(
        self,
        policy: ProbabilityCalibrationPolicy | None = None,
        engine: ProbabilityCalibrationEngine | None = None,
    ):
        self.policy = policy or ProbabilityCalibrationPolicy()
        self.engine = engine or ProbabilityCalibrationEngine(policy=self.policy)

    def analyze(self, predicted_probabilities, outcomes, **kwargs):
        return self.engine.analyze(
            predicted_probabilities=predicted_probabilities,
            outcomes=outcomes,
            **kwargs,
        )

    def calibrate(self, profile, probability: float) -> float:
        return self.engine.calibrate(profile, probability)

    def calibrate_many(self, profile, probabilities):
        return self.engine.calibrate_many(profile, probabilities)
