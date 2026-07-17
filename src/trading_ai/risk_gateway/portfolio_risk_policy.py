from __future__ import annotations
from dataclasses import dataclass

@dataclass(frozen=True)
class PortfolioRiskPolicy:
    maximum_gross_exposure: float = 500000.0
    maximum_net_exposure_absolute: float = 300000.0
    maximum_single_symbol_exposure: float = 100000.0
    maximum_single_symbol_pct_of_net_liquidation: float = 0.20
    maximum_sector_exposure: float = 200000.0
    maximum_sector_pct_of_net_liquidation: float = 0.35
    maximum_position_quantity_equity: float = 10000.0
    maximum_position_contracts_option: int = 500
    maximum_open_positions: int = 200
    maximum_new_positions_per_order: int = 8
    maximum_total_buying_power_utilization: float = 0.75
    minimum_post_trade_buying_power: float = 0.0
    minimum_post_trade_excess_liquidity: float = 0.0
    require_account_match: bool = True
    require_sector_classification: bool = False
    require_position_limit_profile: bool = True
    reject_new_position_when_limit_reached: bool = True
    reject_concentration_limit_breaches: bool = True
    minimum_approval_score: float = 85.0
    fail_closed: bool = True

    def validate(self) -> None:
        for name in (
            "maximum_gross_exposure",
            "maximum_net_exposure_absolute",
            "maximum_single_symbol_exposure",
            "maximum_sector_exposure",
            "maximum_position_quantity_equity",
            "maximum_position_contracts_option",
            "maximum_open_positions",
            "maximum_new_positions_per_order",
        ):
            if getattr(self, name) <= 0:
                raise ValueError(f"{name} must be positive")
        for name in (
            "maximum_single_symbol_pct_of_net_liquidation",
            "maximum_sector_pct_of_net_liquidation",
            "maximum_total_buying_power_utilization",
        ):
            value = getattr(self, name)
            if not 0 < value <= 1:
                raise ValueError(f"{name} must be in (0, 1]")
        if not 0 <= self.minimum_approval_score <= 100:
            raise ValueError("minimum_approval_score must be between 0 and 100")
