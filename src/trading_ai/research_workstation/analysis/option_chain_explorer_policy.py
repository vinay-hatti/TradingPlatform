from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class OptionChainExplorerPolicy:
    minimum_volume: int = 100
    minimum_open_interest: int = 100
    maximum_spread_pct: float = 0.20
    preferred_minimum_dte: int = 20
    preferred_maximum_dte: int = 60
    minimum_contract_score: float = 0.0
    maximum_contracts_per_expiration: int = 50

    volume_weight: float = 0.20
    open_interest_weight: float = 0.25
    spread_weight: float = 0.25
    moneyness_weight: float = 0.15
    greeks_weight: float = 0.15

    def validate(self) -> None:
        weights = (
            self.volume_weight,
            self.open_interest_weight,
            self.spread_weight,
            self.moneyness_weight,
            self.greeks_weight,
        )
        if abs(sum(weights) - 1.0) > 1e-9:
            raise ValueError("Option-chain explorer weights must sum to 1.0.")
        if self.preferred_minimum_dte > self.preferred_maximum_dte:
            raise ValueError("Preferred minimum DTE cannot exceed maximum DTE.")
        if self.maximum_spread_pct < 0:
            raise ValueError("Maximum spread percentage cannot be negative.")
