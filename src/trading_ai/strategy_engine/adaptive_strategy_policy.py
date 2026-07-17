from dataclasses import dataclass, field


@dataclass(frozen=True)
class AdaptiveStrategyPolicy:
    """Governance policy for Phase 10 adaptive strategy selection."""

    minimum_strategy_observations: int = 30
    minimum_context_observations: int = 15
    prior_weight: float = 0.35
    performance_weight: float = 0.30
    regime_weight: float = 0.15
    calibration_weight: float = 0.10
    execution_weight: float = 0.10

    maximum_positive_adjustment: float = 20.0
    maximum_negative_adjustment: float = 30.0
    minimum_allowed_score: float = 45.0
    minimum_confidence_score: float = 40.0
    severe_drawdown_pct: float = 0.20
    minimum_profit_factor: float = 0.75
    minimum_win_rate: float = 0.30

    fallback_to_prior: bool = True
    reject_on_severe_performance: bool = True
    preserve_candidate_score: bool = True

    context_keys: tuple[str, ...] = (
        "market_regime",
        "volatility_regime",
        "direction",
    )
    metadata: dict[str, object] = field(default_factory=dict)

    def normalized_weights(self) -> dict[str, float]:
        values = {
            "prior": max(float(self.prior_weight), 0.0),
            "performance": max(float(self.performance_weight), 0.0),
            "regime": max(float(self.regime_weight), 0.0),
            "calibration": max(float(self.calibration_weight), 0.0),
            "execution": max(float(self.execution_weight), 0.0),
        }
        total = sum(values.values())
        if total <= 0.0:
            return {"prior": 1.0, "performance": 0.0, "regime": 0.0, "calibration": 0.0, "execution": 0.0}
        return {name: value / total for name, value in values.items()}
