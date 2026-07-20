from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CandidateAnalysisPolicy:
    technical_weight: float = 0.20
    liquidity_weight: float = 0.20
    volatility_weight: float = 0.15
    institutional_weight: float = 0.30
    risk_reward_weight: float = 0.15

    ready_threshold: float = 75.0
    watch_threshold: float = 55.0

    strong_volume_threshold: int = 1_000_000
    strong_option_volume_threshold: int = 1_000
    strong_open_interest_threshold: int = 5_000
    maximum_healthy_spread_pct: float = 0.15
    strong_iv_rank_threshold: float = 50.0
    elevated_atr_pct: float = 4.0
    minimum_reward_risk_ratio: float = 1.0
    high_risk_score: float = 70.0

    def validate(self) -> None:
        weights = (
            self.technical_weight,
            self.liquidity_weight,
            self.volatility_weight,
            self.institutional_weight,
            self.risk_reward_weight,
        )
        if any(weight < 0 for weight in weights):
            raise ValueError("Candidate analysis weights cannot be negative.")
        if abs(sum(weights) - 1.0) > 1e-9:
            raise ValueError("Candidate analysis weights must sum to 1.0.")
        if self.watch_threshold > self.ready_threshold:
            raise ValueError(
                "Watch threshold cannot exceed ready threshold."
            )
