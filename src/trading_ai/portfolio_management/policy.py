from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PortfolioAccountPolicy:
    base_currency: str = "USD"
    minimum_initial_capital: float = 1_000.0
    allow_negative_cash: bool = False
    allow_duplicate_open_strategy: bool = False
    maximum_open_positions: int = 100
    contract_multiplier: int = 100

    def validate(self) -> None:
        if self.minimum_initial_capital <= 0:
            raise ValueError("minimum_initial_capital must be positive")
        if self.maximum_open_positions <= 0:
            raise ValueError("maximum_open_positions must be positive")
        if self.contract_multiplier <= 0:
            raise ValueError("contract_multiplier must be positive")
