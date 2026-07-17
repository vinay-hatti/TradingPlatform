from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .feed_monitor_policy import FeedMonitorPolicy
from .feed_monitor_profile import FeedHealthProfile, ReconnectionDecisionProfile


class AutomaticReconnectionGovernance:
    def __init__(self, policy: FeedMonitorPolicy | None = None) -> None:
        self.policy = policy or FeedMonitorPolicy()
        self.policy.validate()
        self._last_attempt_at: dict[str, datetime] = {}

    def evaluate(
        self,
        health: FeedHealthProfile,
        *,
        now: datetime | None = None,
    ) -> ReconnectionDecisionProfile:
        current = now or datetime.now(timezone.utc)
        if current.tzinfo is None:
            current = current.replace(tzinfo=timezone.utc)
        current = current.astimezone(timezone.utc)

        previous = self._last_attempt_at.get(health.provider)
        cooldown_remaining = 0.0
        if previous is not None:
            elapsed = (current - previous).total_seconds()
            cooldown_remaining = max(
                0.0,
                self.policy.reconnect_cooldown_seconds - elapsed,
            )

        reasons: list[str] = []
        if health.reconnect_attempts >= self.policy.maximum_reconnect_attempts:
            reasons.append("MAXIMUM_RECONNECT_ATTEMPTS_EXCEEDED")
        if self.policy.reconnect_only_when_market_open and not health.market_open:
            reasons.append("MARKET_CLOSED")
        if not health.reconnect_allowed:
            reasons.append("RECONNECT_NOT_ALLOWED")
        if cooldown_remaining > 0:
            reasons.append("RECONNECT_COOLDOWN_ACTIVE")

        allowed = not reasons
        action = "RECONNECT" if allowed else "WAIT"
        reason = "STALE_OR_DISCONNECTED_FEED" if allowed else reasons[0]
        if allowed:
            self._last_attempt_at[health.provider] = current

        return ReconnectionDecisionProfile(
            provider=health.provider,
            valid=True,
            allowed=allowed,
            action=action,
            attempt_number=health.reconnect_attempts + 1,
            delay_seconds=health.next_reconnect_delay_seconds,
            cooldown_remaining_seconds=round(cooldown_remaining, 3),
            market_open=health.market_open,
            reason=reason,
            rejection_reasons=tuple(reasons),
            metadata={
                "feed_state": health.state,
                "feed_score": health.score,
            },
        )
