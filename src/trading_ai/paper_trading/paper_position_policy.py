from __future__ import annotations
from dataclasses import dataclass

@dataclass(frozen=True)
class PaperPositionPolicy:
    maximum_positions_per_session: int = 100
    allow_position_netting: bool = True
    allow_scale_in: bool = True
    allow_scale_out: bool = True
    require_positive_mark_price: bool = True
    default_profit_target_pct: float = 0.25
    default_stop_loss_pct: float = 0.15
    default_trailing_stop_pct: float = 0.10
    enable_profit_target_exit: bool = True
    enable_stop_loss_exit: bool = True
    enable_trailing_stop_exit: bool = False
    allow_adjustments: bool = True
    maximum_adjustments_per_position: int = 3
    persist_positions: bool = True
    fail_closed: bool = True

    def validate(self) -> None:
        if self.maximum_positions_per_session <= 0:
            raise ValueError("maximum_positions_per_session must be positive")
        for name in (
            "default_profit_target_pct",
            "default_stop_loss_pct",
            "default_trailing_stop_pct",
        ):
            value = getattr(self, name)
            if not 0 < value <= 1:
                raise ValueError(f"{name} must be in (0, 1]")
        if self.maximum_adjustments_per_position < 0:
            raise ValueError("maximum_adjustments_per_position cannot be negative")
