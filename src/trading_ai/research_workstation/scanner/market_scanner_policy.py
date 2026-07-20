from __future__ import annotations

from dataclasses import dataclass

from .market_scanner_profile import (
    MarketCandidateProfile,
    MarketScanRequestProfile,
)


@dataclass(frozen=True)
class MarketScannerPolicy:
    trend_weight: float = 0.14
    momentum_weight: float = 0.14
    liquidity_weight: float = 0.16
    volatility_weight: float = 0.10
    regime_weight: float = 0.10
    probability_weight: float = 0.18
    expected_return_weight: float = 0.10
    reward_risk_weight: float = 0.08

    maximum_allowed_risk_score: float = 100.0
    minimum_reward_risk_ratio: float = 0.0

    def validate(self) -> None:
        weights = (
            self.trend_weight,
            self.momentum_weight,
            self.liquidity_weight,
            self.volatility_weight,
            self.regime_weight,
            self.probability_weight,
            self.expected_return_weight,
            self.reward_risk_weight,
        )
        if any(weight < 0 for weight in weights):
            raise ValueError("Scanner weights cannot be negative.")
        if abs(sum(weights) - 1.0) > 1e-9:
            raise ValueError("Scanner weights must sum to 1.0.")

    def accepts(
        self,
        candidate: MarketCandidateProfile,
        request: MarketScanRequestProfile,
    ) -> tuple[bool, tuple[str, ...]]:
        filters = request.filters
        reasons: list[str] = []

        if candidate.symbol in filters.excluded_symbols:
            reasons.append("EXCLUDED_SYMBOL")
        if filters.min_price is not None and candidate.price < filters.min_price:
            reasons.append("PRICE_BELOW_MINIMUM")
        if filters.max_price is not None and candidate.price > filters.max_price:
            reasons.append("PRICE_ABOVE_MAXIMUM")
        if (
            filters.min_average_volume is not None
            and candidate.average_volume < filters.min_average_volume
        ):
            reasons.append("AVERAGE_VOLUME_BELOW_MINIMUM")
        if (
            filters.min_option_volume is not None
            and candidate.option_volume < filters.min_option_volume
        ):
            reasons.append("OPTION_VOLUME_BELOW_MINIMUM")
        if (
            filters.min_open_interest is not None
            and candidate.open_interest < filters.min_open_interest
        ):
            reasons.append("OPEN_INTEREST_BELOW_MINIMUM")
        if (
            filters.max_spread_pct is not None
            and candidate.spread_pct > filters.max_spread_pct
        ):
            reasons.append("SPREAD_ABOVE_MAXIMUM")
        if filters.min_iv_rank is not None and candidate.iv_rank < filters.min_iv_rank:
            reasons.append("IV_RANK_BELOW_MINIMUM")
        if (
            filters.min_iv_percentile is not None
            and candidate.iv_percentile < filters.min_iv_percentile
        ):
            reasons.append("IV_PERCENTILE_BELOW_MINIMUM")
        if (
            filters.minimum_atr_pct is not None
            and candidate.atr_pct < filters.minimum_atr_pct
        ):
            reasons.append("ATR_BELOW_MINIMUM")
        if filters.required_regimes and candidate.regime not in filters.required_regimes:
            reasons.append("REGIME_NOT_ALLOWED")
        if filters.required_signals and candidate.signal not in filters.required_signals:
            reasons.append("SIGNAL_NOT_ALLOWED")
        if candidate.risk_score > self.maximum_allowed_risk_score:
            reasons.append("RISK_SCORE_ABOVE_MAXIMUM")
        if candidate.reward_risk_ratio < self.minimum_reward_risk_ratio:
            reasons.append("REWARD_RISK_BELOW_MINIMUM")

        return not reasons, tuple(reasons)
