from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PortfolioAllocationPolicy:
    maximum_portfolio_risk_pct: float = 0.15
    maximum_buying_power_pct: float = 0.65
    maximum_symbol_risk_pct: float = 0.05
    maximum_sector_risk_pct: float = 0.10
    maximum_strategy_risk_pct: float = 0.10
    maximum_correlated_risk_pct: float = 0.12
    maximum_pairwise_correlation: float = 0.80
    target_portfolio_volatility_pct: float = 0.12
    expected_shortfall_limit_pct: float = 0.10
    liquidity_haircut_floor: float = 0.25
    minimum_diversification_score: float = 55.0
    minimum_portfolio_health_score: float = 60.0
    use_fractional_kelly: float = 0.50
    minimum_contracts: int = 1
    maximum_contracts_per_position: int = 100

    def validate(self) -> None:
        bounded = (
            "maximum_portfolio_risk_pct",
            "maximum_buying_power_pct",
            "maximum_symbol_risk_pct",
            "maximum_sector_risk_pct",
            "maximum_strategy_risk_pct",
            "maximum_correlated_risk_pct",
            "maximum_pairwise_correlation",
            "target_portfolio_volatility_pct",
            "expected_shortfall_limit_pct",
            "liquidity_haircut_floor",
            "use_fractional_kelly",
        )
        for name in bounded:
            value = float(getattr(self, name))
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"{name} must be between 0 and 1.")
        if self.minimum_diversification_score < 0:
            raise ValueError("Minimum diversification score cannot be negative.")
        if self.minimum_portfolio_health_score < 0:
            raise ValueError("Minimum portfolio health score cannot be negative.")
        if self.minimum_contracts <= 0:
            raise ValueError("Minimum contracts must be positive.")
        if self.maximum_contracts_per_position < self.minimum_contracts:
            raise ValueError(
                "Maximum contracts per position cannot be below minimum."
            )
