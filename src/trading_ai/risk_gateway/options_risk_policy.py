from __future__ import annotations
from dataclasses import dataclass

@dataclass(frozen=True)
class OptionsRiskPolicy:
    maximum_absolute_delta: float = 10000.0
    maximum_absolute_gamma: float = 5000.0
    maximum_absolute_vega: float = 250000.0
    maximum_absolute_theta: float = 100000.0
    maximum_absolute_rho: float = 100000.0
    maximum_scenario_loss: float = 50000.0
    maximum_scenario_loss_pct_of_net_liquidation: float = 0.20
    maximum_strategy_margin: float = 100000.0
    maximum_margin_utilization: float = 0.50
    require_defined_risk_for_multi_leg_options: bool = True
    reject_uncovered_short_options: bool = True
    reject_missing_greeks: bool = True
    reject_missing_underlying_price: bool = True
    reject_non_positive_underlying_price: bool = True
    allow_long_option_debit_as_defined_risk: bool = True
    option_contract_multiplier: int = 100
    scenario_underlying_shocks_pct: tuple[float, ...] = (-0.20, -0.10, 0.10, 0.20)
    scenario_volatility_shocks: tuple[float, ...] = (-0.10, 0.10)
    scenario_time_decay_days: tuple[int, ...] = (1, 5, 20)
    minimum_approval_score: float = 85.0
    fail_closed: bool = True

    def validate(self) -> None:
        for name in (
            "maximum_absolute_delta", "maximum_absolute_gamma",
            "maximum_absolute_vega", "maximum_absolute_theta",
            "maximum_absolute_rho", "maximum_scenario_loss",
            "maximum_strategy_margin",
        ):
            if getattr(self, name) <= 0:
                raise ValueError(f"{name} must be positive")
        if not 0 < self.maximum_scenario_loss_pct_of_net_liquidation <= 1:
            raise ValueError("maximum_scenario_loss_pct_of_net_liquidation must be in (0, 1]")
        if not 0 < self.maximum_margin_utilization <= 1:
            raise ValueError("maximum_margin_utilization must be in (0, 1]")
        if self.option_contract_multiplier <= 0:
            raise ValueError("option_contract_multiplier must be positive")
        if not self.scenario_underlying_shocks_pct:
            raise ValueError("scenario_underlying_shocks_pct cannot be empty")
        if not 0 <= self.minimum_approval_score <= 100:
            raise ValueError("minimum_approval_score must be between 0 and 100")
