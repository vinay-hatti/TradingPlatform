from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class OptionContractValidationPolicy:
    minimum_strike: float = 0.01
    maximum_strike: float = 1_000_000.0
    minimum_days_to_expiration: int = 0
    maximum_days_to_expiration: int = 1_095
    maximum_spread_percentage: float = 5.0
    maximum_implied_volatility: float = 10.0
    minimum_delta: float = -1.0
    maximum_delta: float = 1.0
    minimum_gamma: float = 0.0
    maximum_gamma: float = 100.0
    minimum_vega: float = 0.0
    maximum_vega: float = 10_000.0
    minimum_theta: float = -10_000.0
    maximum_theta: float = 10_000.0
    require_nonnegative_bid_ask_last: bool = True
    require_nonnegative_volume_open_interest: bool = True
    reject_crossed_market: bool = True
    reject_expired_contracts: bool = True

    def validate(self) -> None:
        if self.minimum_strike <= 0:
            raise ValueError("minimum_strike must be positive")
        if self.maximum_strike < self.minimum_strike:
            raise ValueError("maximum_strike must be >= minimum_strike")
        if self.maximum_days_to_expiration < self.minimum_days_to_expiration:
            raise ValueError(
                "maximum_days_to_expiration must be >= minimum_days_to_expiration"
            )
        if self.maximum_spread_percentage < 0:
            raise ValueError("maximum_spread_percentage must be nonnegative")
        if self.maximum_implied_volatility <= 0:
            raise ValueError("maximum_implied_volatility must be positive")
        if not -1.0 <= self.minimum_delta <= self.maximum_delta <= 1.0:
            raise ValueError("delta bounds must remain within [-1, 1]")
