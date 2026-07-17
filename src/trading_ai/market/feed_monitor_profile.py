from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class FeedHealthCheckProfile:
    name: str
    passed: bool
    required: bool
    score: float
    severity: str
    message: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class FeedHealthProfile:
    provider: str
    valid: bool
    allowed: bool
    state: str
    score: float
    grade: str
    severity: str
    recommendation: str
    market_session: str
    market_open: bool
    connected: bool
    event_silence_seconds: float | None
    heartbeat_silence_seconds: float | None
    stale_feed: bool
    degraded: bool
    reconnect_allowed: bool
    reconnect_attempts: int
    next_reconnect_delay_seconds: float
    checks: tuple[FeedHealthCheckProfile, ...] = ()
    warnings: tuple[str, ...] = ()
    rejection_reasons: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)
    evaluated_at: str = field(default_factory=utc_now_iso)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ReconnectionDecisionProfile:
    provider: str
    valid: bool
    allowed: bool
    action: str
    attempt_number: int
    delay_seconds: float
    cooldown_remaining_seconds: float
    market_open: bool
    reason: str
    warnings: tuple[str, ...] = ()
    rejection_reasons: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)
    evaluated_at: str = field(default_factory=utc_now_iso)
