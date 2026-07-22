from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class OptionChainCoveragePolicy:
    minimum_contracts_per_symbol: int = 20
    review_contracts_per_symbol: int = 10

    minimum_expirations_per_symbol: int = 2
    review_expirations_per_symbol: int = 1

    minimum_strikes_per_expiration: int = 5
    review_strikes_per_expiration: int = 3

    minimum_call_put_balance_score: float = 0.70
    review_call_put_balance_score: float = 0.45

    minimum_strike_surface_score: float = 0.70
    review_strike_surface_score: float = 0.45

    minimum_expiration_coverage_score: float = 0.70
    review_expiration_coverage_score: float = 0.45

    ready_overall_score: float = 0.75
    review_overall_score: float = 0.45

    maximum_acceptable_strike_gap_multiple: float = 2.50

    @staticmethod
    def clamp(value: float) -> float:
        return max(0.0, min(1.0, float(value)))
