from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AutomatedPaperOrderHandoffPolicy:
    environment: str = "PAPER"
    live_trading_enabled: bool = False
    default_mode: str = "DRY_RUN"
    require_institutional_approval: bool = True
    require_risk_gateway_approval: bool = True
    minimum_decision_score: float = 60.0
    minimum_probability: float = 0.50
    maximum_quantity: float = 100.0
    maximum_order_notional: float = 5_000.0
    maximum_option_contracts: float = 10.0
    allowed_asset_classes: tuple[str, ...] = ("EQUITY", "STOCK", "OPTION")
    allowed_sides: tuple[str, ...] = ("BUY", "SELL")
    allowed_order_types: tuple[str, ...] = ("MARKET", "LIMIT", "STOP", "STOP_LIMIT")
    allowed_time_in_force: tuple[str, ...] = ("DAY", "GTC")
    require_limit_orders_for_automated_entries: bool = True
    allow_outside_regular_hours: bool = False

    def validate(self) -> None:
        if self.environment != "PAPER":
            raise ValueError("automated handoff policy must remain PAPER")
        if self.live_trading_enabled:
            raise ValueError("live trading cannot be enabled")
        if self.default_mode not in {"DRY_RUN", "SUBMIT"}:
            raise ValueError("unsupported default_mode")
        if not 0.0 <= self.minimum_probability <= 1.0:
            raise ValueError("minimum_probability must be within [0, 1]")
        if self.maximum_quantity <= 0 or self.maximum_order_notional <= 0:
            raise ValueError("quantity and notional limits must be positive")
