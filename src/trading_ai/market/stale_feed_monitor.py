from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .feed_monitor_policy import FeedMonitorPolicy
from .feed_monitor_profile import FeedHealthCheckProfile, FeedHealthProfile
from .market_hours_profile import MarketSessionProfile
from .realtime_provider_profile import ProviderConnectionProfile


def _parse(value: str | datetime | None) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        result = value
    else:
        result = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if result.tzinfo is None:
        result = result.replace(tzinfo=timezone.utc)
    return result.astimezone(timezone.utc)


class StaleFeedMonitor:
    def __init__(self, policy: FeedMonitorPolicy | None = None) -> None:
        self.policy = policy or FeedMonitorPolicy()
        self.policy.validate()

    @staticmethod
    def _grade(score: float) -> tuple[str, str]:
        if score >= 95:
            return "A", "LOW"
        if score >= 85:
            return "B", "MODERATE"
        if score >= 70:
            return "C", "SEVERE"
        return "F", "CRITICAL"

    def evaluate(
        self,
        connection: ProviderConnectionProfile | dict[str, Any],
        market_session: MarketSessionProfile,
        *,
        last_event_at: str | datetime | None = None,
        now: datetime | None = None,
    ) -> FeedHealthProfile:
        current = now or datetime.now(timezone.utc)
        if current.tzinfo is None:
            current = current.replace(tzinfo=timezone.utc)
        current = current.astimezone(timezone.utc)

        def value(name: str, default: Any = None) -> Any:
            if isinstance(connection, dict):
                return connection.get(name, default)
            return getattr(connection, name, default)

        provider = str(value("provider", "unknown"))
        connected = bool(value("connected", False))
        heartbeat = _parse(value("last_heartbeat_at", None))
        event_time = _parse(last_event_at)
        event_silence = (
            (current - event_time).total_seconds() if event_time else None
        )
        heartbeat_silence = (
            (current - heartbeat).total_seconds() if heartbeat else None
        )

        checks: list[FeedHealthCheckProfile] = []

        def add(
            name: str,
            passed: bool,
            required: bool,
            message: str,
            metadata: dict[str, Any] | None = None,
        ) -> None:
            checks.append(
                FeedHealthCheckProfile(
                    name=name,
                    passed=passed,
                    required=required,
                    score=100.0 if passed else 0.0,
                    severity="LOW" if passed else "CRITICAL",
                    message=message,
                    metadata=metadata or {},
                )
            )

        add("connection", connected, True, "Provider connection is active.")
        event_ok = (
            event_silence is None
            or event_silence <= self.policy.maximum_event_silence_seconds
            or not market_session.market_open
        )
        add(
            "event_freshness",
            event_ok,
            market_session.market_open,
            "Market event flow is fresh.",
            {"event_silence_seconds": event_silence},
        )
        heartbeat_ok = (
            not self.policy.require_heartbeat
            or heartbeat_silence is None
            or heartbeat_silence <= self.policy.maximum_heartbeat_silence_seconds
        )
        add(
            "heartbeat_freshness",
            heartbeat_ok,
            self.policy.require_heartbeat,
            "Provider heartbeat is fresh.",
            {"heartbeat_silence_seconds": heartbeat_silence},
        )

        stale = not event_ok or not heartbeat_ok
        degraded = bool(
            (event_silence is not None and event_silence > self.policy.degraded_event_silence_seconds)
            or (
                heartbeat_silence is not None
                and heartbeat_silence > self.policy.degraded_heartbeat_silence_seconds
            )
        )
        required = [item for item in checks if item.required]
        failed = [item for item in required if not item.passed]
        score = sum(item.score for item in required) / len(required) if required else 100.0
        allowed = not failed and score >= self.policy.minimum_health_score
        grade, severity = self._grade(score)

        attempts = int(value("reconnect_attempts", 0) or 0)
        reconnect_allowed = (
            (not connected or stale)
            and attempts < self.policy.maximum_reconnect_attempts
            and (
                market_session.market_open
                or not self.policy.reconnect_only_when_market_open
            )
        )
        delay = min(
            self.policy.reconnect_initial_delay_seconds
            * (self.policy.reconnect_multiplier ** max(attempts, 0)),
            self.policy.reconnect_max_delay_seconds,
        )

        if allowed:
            state = "HEALTHY"
            recommendation = "CONTINUE"
        elif reconnect_allowed:
            state = "STALE" if stale else "DISCONNECTED"
            recommendation = "RECONNECT"
        else:
            state = "FAILED" if attempts >= self.policy.maximum_reconnect_attempts else "CLOSED"
            recommendation = "STOP" if state == "FAILED" else "WAIT"

        warnings: list[str] = []
        if degraded and not stale:
            warnings.append("FEED_DEGRADED")
        if not market_session.market_open:
            warnings.append("MARKET_CLOSED")

        return FeedHealthProfile(
            provider=provider,
            valid=True,
            allowed=allowed,
            state=state,
            score=round(score, 2),
            grade=grade,
            severity=severity,
            recommendation=recommendation,
            market_session=market_session.session,
            market_open=market_session.market_open,
            connected=connected,
            event_silence_seconds=round(event_silence, 3) if event_silence is not None else None,
            heartbeat_silence_seconds=round(heartbeat_silence, 3) if heartbeat_silence is not None else None,
            stale_feed=stale,
            degraded=degraded,
            reconnect_allowed=reconnect_allowed,
            reconnect_attempts=attempts,
            next_reconnect_delay_seconds=delay,
            checks=tuple(checks),
            warnings=tuple(warnings),
            rejection_reasons=tuple(item.name.upper() for item in failed),
            metadata={"connection_state": value("state", "UNKNOWN")},
        )
