from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FeedMonitorPolicy:
    maximum_event_silence_seconds: float = 10.0
    maximum_heartbeat_silence_seconds: float = 30.0
    degraded_event_silence_seconds: float = 5.0
    degraded_heartbeat_silence_seconds: float = 15.0
    maximum_reconnect_attempts: int = 10
    reconnect_initial_delay_seconds: float = 1.0
    reconnect_max_delay_seconds: float = 60.0
    reconnect_multiplier: float = 2.0
    reconnect_cooldown_seconds: float = 1.0
    reconnect_only_when_market_open: bool = True
    require_heartbeat: bool = True
    fail_closed: bool = True
    minimum_health_score: float = 85.0

    def validate(self) -> None:
        if self.maximum_event_silence_seconds <= 0:
            raise ValueError("maximum_event_silence_seconds must be positive")
        if self.maximum_heartbeat_silence_seconds <= 0:
            raise ValueError("maximum_heartbeat_silence_seconds must be positive")
        if self.degraded_event_silence_seconds > self.maximum_event_silence_seconds:
            raise ValueError("degraded event threshold cannot exceed maximum")
        if self.degraded_heartbeat_silence_seconds > self.maximum_heartbeat_silence_seconds:
            raise ValueError("degraded heartbeat threshold cannot exceed maximum")
        if self.maximum_reconnect_attempts < 0:
            raise ValueError("maximum_reconnect_attempts cannot be negative")
        if self.reconnect_multiplier < 1.0:
            raise ValueError("reconnect_multiplier must be at least one")
        if not 0.0 <= self.minimum_health_score <= 100.0:
            raise ValueError("minimum_health_score must be between 0 and 100")
