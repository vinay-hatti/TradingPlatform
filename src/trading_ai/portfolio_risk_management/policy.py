from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class PortfolioRiskPolicy:
    maximum_capital_utilization_pct: float = 50.0
    minimum_cash_reserve_pct: float = 20.0
    maximum_symbol_concentration_pct: float = 25.0
    maximum_sector_concentration_pct: float = 40.0
    maximum_strategy_concentration_pct: float = 40.0
    maximum_direction_concentration_pct: float = 70.0
    maximum_correlation_group_pct: float = 35.0
    maximum_portfolio_loss_pct: float = 20.0
    maximum_stress_loss_pct: float = 12.0
    maximum_delta_abs: float = 500.0
    maximum_gamma_abs: float = 100.0
    maximum_theta_abs: float = 500.0
    maximum_vega_abs: float = 1000.0
    maximum_rho_abs: float = 1000.0
    maximum_illiquid_capital_pct: float = 20.0
    warning_utilization_pct: float = 80.0
    block_on_critical_breach: bool = True
    reduce_only_on_high_breach: bool = True

    def validate(self) -> None:
        pct_fields = (
            self.maximum_capital_utilization_pct,
            self.minimum_cash_reserve_pct,
            self.maximum_symbol_concentration_pct,
            self.maximum_sector_concentration_pct,
            self.maximum_strategy_concentration_pct,
            self.maximum_direction_concentration_pct,
            self.maximum_correlation_group_pct,
            self.maximum_portfolio_loss_pct,
            self.maximum_stress_loss_pct,
            self.maximum_illiquid_capital_pct,
            self.warning_utilization_pct,
        )
        if any(value < 0 or value > 100 for value in pct_fields):
            raise ValueError("percentage policy values must be between 0 and 100")
        for value in (
            self.maximum_delta_abs,
            self.maximum_gamma_abs,
            self.maximum_theta_abs,
            self.maximum_vega_abs,
            self.maximum_rho_abs,
        ):
            if value <= 0:
                raise ValueError("Greek limits must be positive")

    def to_dict(self) -> dict:
        return asdict(self)
