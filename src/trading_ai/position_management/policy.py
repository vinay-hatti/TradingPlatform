from __future__ import annotations
from dataclasses import dataclass

@dataclass(frozen=True)
class PositionManagementPolicy:
    take_profit_pct: float = 0.50
    partial_profit_pct: float = 0.30
    partial_profit_fraction: float = 0.50
    stop_loss_pct: float = -0.35
    max_holding_days: int = 30
    stale_mark_minutes: int = 60
    minimum_mark_price: float = 0.01
    allow_automatic_close: bool = False
    require_risk_gate: bool = True
    default_order_type: str = "LIMIT"
    limit_offset_pct: float = 0.02

    def validate(self) -> None:
        if not 0 < self.partial_profit_pct < self.take_profit_pct:
            raise ValueError("partial_profit_pct must be between zero and take_profit_pct")
        if not 0 < self.partial_profit_fraction <= 1:
            raise ValueError("partial_profit_fraction must be in (0, 1]")
        if self.stop_loss_pct >= 0:
            raise ValueError("stop_loss_pct must be negative")
        if self.max_holding_days < 1 or self.stale_mark_minutes < 1:
            raise ValueError("holding and stale thresholds must be positive")
