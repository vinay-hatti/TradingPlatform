from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class InstitutionalExplainabilityPolicy:
    technical_weight: float = 0.15
    liquidity_weight: float = 0.15
    volatility_weight: float = 0.10
    institutional_weight: float = 0.30
    risk_reward_weight: float = 0.20
    payoff_weight: float = 0.10

    bullish_price_shock_pct: float = 0.10
    bearish_price_shock_pct: float = -0.10
    volatility_expansion_points: float = 10.0
    volatility_contraction_points: float = -10.0
    time_decay_days: int = 7

    strong_positive_threshold: float = 10.0
    material_threshold: float = 4.0
    approval_threshold: float = 70.0
    watch_threshold: float = 50.0
    maximum_high_risk_scenarios: int = 1

    def validate(self) -> None:
        weights = (
            self.technical_weight,
            self.liquidity_weight,
            self.volatility_weight,
            self.institutional_weight,
            self.risk_reward_weight,
            self.payoff_weight,
        )
        if any(weight < 0 for weight in weights):
            raise ValueError("Explainability weights cannot be negative.")
        if abs(sum(weights) - 1.0) > 1e-9:
            raise ValueError("Explainability weights must sum to 1.0.")
        if self.watch_threshold > self.approval_threshold:
            raise ValueError(
                "Watch threshold cannot exceed approval threshold."
            )
        if self.time_decay_days < 0:
            raise ValueError("Time-decay scenario days cannot be negative.")
