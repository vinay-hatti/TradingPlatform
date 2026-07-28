from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AutomatedPositionManagementPolicy:
    environment: str = "PAPER"
    live_trading_enabled: bool = False
    take_profit_pct: float = 20.0
    stop_loss_pct: float = -10.0
    trailing_stop_pct: float = 8.0
    maximum_holding_minutes: int = 10_080
    option_exit_dte: int = 3
    maximum_exit_orders_per_run: int = 10
    exit_order_type: str = "LIMIT"
    time_in_force: str = "DAY"
    limit_offset_pct: float = 0.50
    require_positive_market_price: bool = True
    submission_confirmation_template: str = (
        "SUBMIT AUTOMATED PAPER EXITS {portfolio_id}"
    )

    def validate(self) -> None:
        if self.environment != "PAPER":
            raise ValueError("position management must remain PAPER")
        if self.live_trading_enabled:
            raise ValueError("live trading cannot be enabled")
        if self.take_profit_pct <= 0:
            raise ValueError("take_profit_pct must be positive")
        if self.stop_loss_pct >= 0:
            raise ValueError("stop_loss_pct must be negative")
        if self.trailing_stop_pct <= 0:
            raise ValueError("trailing_stop_pct must be positive")
        if self.maximum_holding_minutes < 1:
            raise ValueError("maximum_holding_minutes must be positive")
        if self.option_exit_dte < 0:
            raise ValueError("option_exit_dte cannot be negative")
        if self.maximum_exit_orders_per_run < 1:
            raise ValueError("maximum_exit_orders_per_run must be positive")
        if self.exit_order_type != "LIMIT":
            raise ValueError("automated exits currently require LIMIT orders")
        if not 0.0 <= self.limit_offset_pct <= 10.0:
            raise ValueError("limit_offset_pct must be within [0, 10]")
