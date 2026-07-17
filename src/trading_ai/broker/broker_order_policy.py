from dataclasses import dataclass

@dataclass(frozen=True)
class BrokerOrderPolicy:
    allowed_sides: tuple[str, ...] = ("BUY", "SELL", "BUY_TO_OPEN", "SELL_TO_OPEN", "BUY_TO_CLOSE", "SELL_TO_CLOSE")
    allowed_order_types: tuple[str, ...] = ("MARKET", "LIMIT", "STOP", "STOP_LIMIT")
    allowed_time_in_force: tuple[str, ...] = ("DAY", "GTC", "IOC", "FOK")
    allowed_position_effects: tuple[str, ...] = ("OPEN", "CLOSE", "AUTO")
    minimum_quantity: float = 1.0
    maximum_quantity: float = 1000000.0
    maximum_legs: int = 8
    require_limit_price_for_limit_orders: bool = True
    require_stop_price_for_stop_orders: bool = True
    reject_market_multi_leg_orders: bool = True
    require_same_underlying_for_multi_leg: bool = True
    require_unique_client_order_id: bool = True
    fail_closed: bool = True
    minimum_validation_score: float = 85.0

    def validate(self) -> None:
        if self.minimum_quantity <= 0: raise ValueError("minimum_quantity must be positive")
        if self.maximum_quantity < self.minimum_quantity: raise ValueError("maximum_quantity cannot be below minimum")
        if self.maximum_legs <= 0: raise ValueError("maximum_legs must be positive")
        if not 0 <= self.minimum_validation_score <= 100: raise ValueError("minimum_validation_score invalid")
