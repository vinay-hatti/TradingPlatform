from __future__ import annotations
from dataclasses import dataclass

@dataclass(frozen=True)
class OrderLifecyclePolicy:
    allowed_order_types: tuple[str, ...] = ("MARKET", "LIMIT", "STOP", "STOP_LIMIT")
    allowed_time_in_force: tuple[str, ...] = ("DAY", "GTC", "IOC", "FOK")
    allowed_sides: tuple[str, ...] = ("BUY", "SELL", "BUY_TO_OPEN", "SELL_TO_OPEN", "BUY_TO_CLOSE", "SELL_TO_CLOSE")
    allowed_position_effects: tuple[str, ...] = ("OPEN", "CLOSE", "AUTO")
    terminal_states: tuple[str, ...] = ("FILLED", "CANCELED", "REJECTED", "EXPIRED")
    maximum_legs: int = 8
    minimum_quantity: float = 1.0
    maximum_quantity: float = 1_000_000.0
    require_client_order_id: bool = True
    require_account_id: bool = True
    require_idempotency_key: bool = True
    require_limit_price_for_limit_orders: bool = True
    require_stop_price_for_stop_orders: bool = True
    reject_market_multi_leg_orders: bool = True
    reject_transitions_from_terminal_states: bool = True
    reject_fill_quantity_regression: bool = True
    reject_overfills: bool = True
    allow_partial_fill_cancel: bool = True
    fail_closed: bool = True

    def validate(self) -> None:
        if self.maximum_legs <= 0:
            raise ValueError("maximum_legs must be positive")
        if self.minimum_quantity <= 0:
            raise ValueError("minimum_quantity must be positive")
        if self.maximum_quantity < self.minimum_quantity:
            raise ValueError("maximum_quantity cannot be below minimum_quantity")
        if not self.terminal_states:
            raise ValueError("terminal_states cannot be empty")
