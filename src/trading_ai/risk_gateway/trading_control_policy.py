from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TradingControlPolicy:
    """Daily loss, drawdown, kill-switch, and trading-halt governance."""

    maximum_daily_realized_loss: float = 10000.0
    maximum_daily_total_loss: float = 15000.0
    maximum_intraday_drawdown: float = 20000.0
    maximum_drawdown_pct_of_starting_equity: float = 0.10
    maximum_consecutive_losing_trades: int = 5
    maximum_rejected_orders_per_session: int = 20
    maximum_risk_breaches_per_session: int = 5
    halt_on_daily_realized_loss: bool = True
    halt_on_daily_total_loss: bool = True
    halt_on_drawdown: bool = True
    halt_on_consecutive_losses: bool = True
    halt_on_rejected_orders: bool = False
    halt_on_risk_breaches: bool = True
    reject_when_manual_kill_switch_active: bool = True
    reject_when_automatic_kill_switch_active: bool = True
    reject_when_account_halted: bool = True
    reject_when_symbol_halted: bool = True
    reject_when_sector_halted: bool = True
    allow_reduce_only_during_halt: bool = True
    require_control_state: bool = True
    minimum_approval_score: float = 85.0
    fail_closed: bool = True

    def validate(self) -> None:
        for name in (
            "maximum_daily_realized_loss",
            "maximum_daily_total_loss",
            "maximum_intraday_drawdown",
        ):
            if getattr(self, name) <= 0:
                raise ValueError(f"{name} must be positive")
        if not 0 < self.maximum_drawdown_pct_of_starting_equity <= 1:
            raise ValueError(
                "maximum_drawdown_pct_of_starting_equity must be in (0, 1]"
            )
        for name in (
            "maximum_consecutive_losing_trades",
            "maximum_rejected_orders_per_session",
            "maximum_risk_breaches_per_session",
        ):
            if getattr(self, name) <= 0:
                raise ValueError(f"{name} must be positive")
        if not 0 <= self.minimum_approval_score <= 100:
            raise ValueError(
                "minimum_approval_score must be between 0 and 100"
            )
