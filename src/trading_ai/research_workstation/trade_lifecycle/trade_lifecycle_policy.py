from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TradeLifecyclePolicy:
    minimum_days_to_expiration: int = 7
    preferred_entry_dte_min: int = 21
    preferred_entry_dte_max: int = 60
    minimum_entry_confidence: float = 0.60
    maximum_entry_spread_pct: float = 0.20
    profit_target_pct_of_max_profit: float = 0.50
    stop_loss_multiple_of_credit: float = 2.00
    maximum_loss_pct: float = 0.75
    exit_days_to_expiration: int = 7
    adjustment_days_to_expiration: int = 14
    adjustment_loss_trigger_pct: float = 0.35
    delta_adjustment_trigger: float = 0.30
    event_risk_exit_days: int = 2
    allow_rolls: bool = True
    allow_reduce_size: bool = True
    allow_hedges: bool = True
    require_defined_risk: bool = True

    def validate(self) -> None:
        if self.minimum_days_to_expiration < 0:
            raise ValueError("Minimum DTE cannot be negative.")
        if self.preferred_entry_dte_min < self.minimum_days_to_expiration:
            raise ValueError(
                "Preferred entry minimum DTE cannot be below minimum DTE."
            )
        if self.preferred_entry_dte_max < self.preferred_entry_dte_min:
            raise ValueError(
                "Preferred entry maximum DTE cannot be below minimum."
            )
        bounded = (
            "minimum_entry_confidence",
            "maximum_entry_spread_pct",
            "profit_target_pct_of_max_profit",
            "maximum_loss_pct",
            "adjustment_loss_trigger_pct",
            "delta_adjustment_trigger",
        )
        for name in bounded:
            value = float(getattr(self, name))
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"{name} must be between 0 and 1.")
        if self.stop_loss_multiple_of_credit <= 0:
            raise ValueError("Stop-loss multiple must be positive.")
