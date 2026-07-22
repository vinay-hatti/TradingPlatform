from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class OptionChainQualityPolicy:
    minimum_contracts_per_symbol: int = 10

    minimum_quote_completeness: float = 0.60
    review_quote_completeness: float = 0.30

    minimum_trade_completeness: float = 0.35
    review_trade_completeness: float = 0.10

    minimum_liquidity_score: float = 0.50
    review_liquidity_score: float = 0.20

    minimum_spread_integrity_score: float = 0.90
    review_spread_integrity_score: float = 0.70

    minimum_iv_completeness: float = 0.70
    review_iv_completeness: float = 0.40

    minimum_greeks_completeness: float = 0.65
    review_greeks_completeness: float = 0.35

    ready_overall_score: float = 0.72
    review_overall_score: float = 0.42

    minimum_volume: int = 100
    minimum_open_interest: int = 100
    maximum_spread_pct: float = 0.40

    @staticmethod
    def clamp(value: float) -> float:
        return max(0.0, min(1.0, float(value)))
