from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TradeConstructionPolicy:
    contract_multiplier: int = 100
    minimum_contracts: int = 1
    maximum_contracts: int = 100
    maximum_position_risk_pct: float = 0.05
    maximum_buying_power_pct: float = 0.20
    minimum_reward_risk_ratio: float = 1.0
    minimum_probability_of_profit: float = 0.50
    maximum_bid_ask_spread_pct: float = 0.25
    minimum_open_interest: int = 100
    minimum_option_volume: int = 25
    limit_price_buffer_pct: float = 0.02
    require_defined_risk_for_approval: bool = True

    def validate(self) -> None:
        if self.contract_multiplier <= 0:
            raise ValueError("Contract multiplier must be positive.")
        if self.minimum_contracts <= 0:
            raise ValueError("Minimum contracts must be positive.")
        if self.maximum_contracts < self.minimum_contracts:
            raise ValueError(
                "Maximum contracts cannot be below minimum contracts."
            )
        for name, value in (
            ("maximum_position_risk_pct", self.maximum_position_risk_pct),
            ("maximum_buying_power_pct", self.maximum_buying_power_pct),
            ("minimum_probability_of_profit", self.minimum_probability_of_profit),
            ("maximum_bid_ask_spread_pct", self.maximum_bid_ask_spread_pct),
            ("limit_price_buffer_pct", self.limit_price_buffer_pct),
        ):
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"{name} must be between 0 and 1.")
        if self.minimum_reward_risk_ratio < 0:
            raise ValueError(
                "Minimum reward/risk ratio cannot be negative."
            )
