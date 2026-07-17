from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PreTradeRiskPolicy:
    """Order-level pre-trade risk governance."""

    maximum_order_notional: float = 100000.0
    maximum_order_premium: float = 25000.0
    maximum_contracts_per_order: int = 100
    maximum_equity_quantity: float = 10000.0
    maximum_order_pct_of_buying_power: float = 0.25
    maximum_order_pct_of_net_liquidation: float = 0.10
    minimum_available_buying_power: float = 0.0
    require_positive_buying_power: bool = True
    require_positive_net_liquidation: bool = True
    require_defined_risk_for_multi_leg_options: bool = False
    reject_undefined_risk_option_orders: bool = False
    reject_zero_or_negative_price: bool = True
    reject_zero_or_negative_quantity: bool = True
    reject_missing_market_price: bool = True
    reject_missing_account_profile: bool = True
    allow_market_orders_without_limit_price: bool = True
    option_contract_multiplier: int = 100
    minimum_approval_score: float = 85.0
    fail_closed: bool = True

    def validate(self) -> None:
        if self.maximum_order_notional <= 0:
            raise ValueError("maximum_order_notional must be positive")
        if self.maximum_order_premium <= 0:
            raise ValueError("maximum_order_premium must be positive")
        if self.maximum_contracts_per_order <= 0:
            raise ValueError("maximum_contracts_per_order must be positive")
        if self.maximum_equity_quantity <= 0:
            raise ValueError("maximum_equity_quantity must be positive")
        if not 0 < self.maximum_order_pct_of_buying_power <= 1:
            raise ValueError("maximum_order_pct_of_buying_power must be in (0, 1]")
        if not 0 < self.maximum_order_pct_of_net_liquidation <= 1:
            raise ValueError("maximum_order_pct_of_net_liquidation must be in (0, 1]")
        if self.option_contract_multiplier <= 0:
            raise ValueError("option_contract_multiplier must be positive")
        if not 0 <= self.minimum_approval_score <= 100:
            raise ValueError("minimum_approval_score must be between 0 and 100")
