from trading_ai.strategy_engine.probability_engine import (
    ProbabilityEngine,
)
from trading_ai.strategy_engine.probability_policy import (
    ProbabilityPolicy,
)


class ProbabilityService:
    def __init__(
        self,
        policy: ProbabilityPolicy | None = None,
        engine: ProbabilityEngine | None = None,
    ):
        self.policy = (
            policy
            or ProbabilityPolicy()
        )

        self.engine = (
            engine
            or ProbabilityEngine(
                policy=self.policy
            )
        )

    def analyze(
        self,
        structure,
        volatility,
        horizon_days,
        **kwargs,
    ):
        return self.engine.analyze(
            structure=structure,
            volatility=volatility,
            horizon_days=horizon_days,
            **kwargs,
        )
