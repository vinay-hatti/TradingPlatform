from dataclasses import dataclass


@dataclass(frozen=True)
class StrategyScoreWeights:
    """
    Default institutional score weights.

    Total weight must equal 1.00.
    """

    technical: float = 0.15
    volatility: float = 0.10
    expected_move: float = 0.10
    strategy_selection: float = 0.10
    strike: float = 0.10
    expiration: float = 0.10
    greeks: float = 0.10
    liquidity: float = 0.10
    execution: float = 0.05
    risk_reward: float = 0.05
    data_confidence: float = 0.03
    portfolio_fit: float = 0.02

    def as_dict(self) -> dict[str, float]:
        return {
            "technical": self.technical,
            "volatility": self.volatility,
            "expected_move": self.expected_move,
            "strategy_selection": self.strategy_selection,
            "strike": self.strike,
            "expiration": self.expiration,
            "greeks": self.greeks,
            "liquidity": self.liquidity,
            "execution": self.execution,
            "risk_reward": self.risk_reward,
            "data_confidence": self.data_confidence,
            "portfolio_fit": self.portfolio_fit,
        }

    def validate(self) -> None:
        weights = self.as_dict()

        for name, value in weights.items():
            if value < 0:
                raise ValueError(
                    f"Strategy score weight '{name}' cannot be negative"
                )

        total = sum(weights.values())

        if abs(total - 1.0) > 0.000001:
            raise ValueError(
                f"Strategy score weights must total 1.00; received {total:.6f}"
            )
