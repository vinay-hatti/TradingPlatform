from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RealTimeProviderPolicy:
    connection_timeout_seconds: float = 15.0
    heartbeat_timeout_seconds: float = 30.0
    reconnect_initial_delay_seconds: float = 1.0
    reconnect_max_delay_seconds: float = 60.0
    reconnect_multiplier: float = 2.0
    maximum_reconnect_attempts: int = 10
    maximum_symbols_per_subscription: int = 1000
    allow_duplicate_subscriptions: bool = False
    require_heartbeat: bool = True
    fail_closed: bool = True

    def validate(self) -> None:
        if self.connection_timeout_seconds <= 0:
            raise ValueError("connection_timeout_seconds must be positive")
        if self.heartbeat_timeout_seconds <= 0:
            raise ValueError("heartbeat_timeout_seconds must be positive")
        if self.reconnect_initial_delay_seconds < 0:
            raise ValueError("reconnect_initial_delay_seconds cannot be negative")
        if self.reconnect_max_delay_seconds < self.reconnect_initial_delay_seconds:
            raise ValueError("reconnect_max_delay_seconds cannot be below initial delay")
        if self.reconnect_multiplier < 1.0:
            raise ValueError("reconnect_multiplier must be at least 1")
        if self.maximum_reconnect_attempts < 0:
            raise ValueError("maximum_reconnect_attempts cannot be negative")
        if self.maximum_symbols_per_subscription <= 0:
            raise ValueError("maximum_symbols_per_subscription must be positive")
