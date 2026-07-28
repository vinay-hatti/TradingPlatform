from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AutomatedPortfolioManagementPolicy:
    environment: str = "PAPER"
    live_trading_enabled: bool = False
    maximum_symbol_allocation_pct: float = 20.0
    maximum_sector_allocation_pct: float = 35.0
    maximum_industry_allocation_pct: float = 25.0
    maximum_gross_exposure_pct: float = 100.0
    maximum_net_exposure_pct: float = 80.0
    maximum_capital_utilization_pct: float = 75.0
    maximum_margin_utilization_pct: float = 50.0
    maximum_daily_loss_pct: float = 3.0
    maximum_drawdown_pct: float = 10.0
    maximum_open_positions: int = 20
    maximum_option_contracts: int = 100
    maximum_absolute_delta_notional_pct: float = 50.0
    maximum_absolute_gamma_notional_pct: float = 10.0
    maximum_absolute_vega_notional_pct: float = 20.0
    minimum_cash_pct: float = 20.0
    minimum_health_score: float = 70.0

    def validate(self) -> None:
        if self.environment != "PAPER":
            raise ValueError("portfolio management must remain PAPER")
        if self.live_trading_enabled:
            raise ValueError("live trading cannot be enabled")
        percentage_fields = (
            "maximum_symbol_allocation_pct",
            "maximum_sector_allocation_pct",
            "maximum_industry_allocation_pct",
            "maximum_gross_exposure_pct",
            "maximum_net_exposure_pct",
            "maximum_capital_utilization_pct",
            "maximum_margin_utilization_pct",
            "maximum_daily_loss_pct",
            "maximum_drawdown_pct",
            "maximum_absolute_delta_notional_pct",
            "maximum_absolute_gamma_notional_pct",
            "maximum_absolute_vega_notional_pct",
            "minimum_cash_pct",
            "minimum_health_score",
        )
        for name in percentage_fields:
            value = float(getattr(self, name))
            if not 0.0 <= value <= 100.0:
                raise ValueError(f"{name} must be within [0, 100]")
        if self.maximum_open_positions < 1:
            raise ValueError("maximum_open_positions must be positive")
        if self.maximum_option_contracts < 1:
            raise ValueError("maximum_option_contracts must be positive")
