from __future__ import annotations

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from trading_ai.market.feed_monitor_policy import FeedMonitorPolicy
from trading_ai.market.market_hours_service import MarketHoursService
from trading_ai.market.paper_streaming_adapter import PaperStreamingAdapter
from trading_ai.market.reconnection_governance import (
    AutomaticReconnectionGovernance,
)
from trading_ai.market.realtime_provider_service import RealTimeProviderService
from trading_ai.market.stale_feed_monitor import StaleFeedMonitor


def main() -> None:
    eastern = ZoneInfo("America/New_York")
    service = MarketHoursService(
        holidays=("2026-07-03",),
        early_closes={"2026-11-27": "13:00"},
    )

    regular = service.evaluate(
        datetime(2026, 7, 14, 10, 0, tzinfo=eastern)
    )
    assert regular.market_open
    assert regular.regular_session
    assert regular.session == "REGULAR"

    premarket = service.evaluate(
        datetime(2026, 7, 14, 8, 0, tzinfo=eastern)
    )
    assert premarket.market_open
    assert premarket.session == "PREMARKET"

    holiday = service.evaluate(
        datetime(2026, 7, 3, 10, 0, tzinfo=eastern)
    )
    assert not holiday.market_open
    assert holiday.session == "HOLIDAY"

    early = service.evaluate(
        datetime(2026, 11, 27, 12, 30, tzinfo=eastern)
    )
    assert early.market_open
    assert early.early_close
    assert "EARLY_CLOSE_SESSION" in early.warnings

    policy = FeedMonitorPolicy(
        maximum_event_silence_seconds=10,
        maximum_heartbeat_silence_seconds=30,
        degraded_event_silence_seconds=5,
        degraded_heartbeat_silence_seconds=15,
        maximum_reconnect_attempts=3,
        reconnect_cooldown_seconds=5,
    )
    adapter = PaperStreamingAdapter()
    provider_service = RealTimeProviderService(adapter)
    provider_service.connect()
    provider_service.lifecycle.heartbeat()

    now = datetime.now(timezone.utc)
    monitor = StaleFeedMonitor(policy)
    healthy = monitor.evaluate(
        provider_service.lifecycle.profile,
        regular,
        last_event_at=now - timedelta(seconds=1),
        now=now,
    )
    assert healthy.allowed
    assert healthy.state == "HEALTHY"
    assert healthy.recommendation == "CONTINUE"

    stale = monitor.evaluate(
        provider_service.lifecycle.profile,
        regular,
        last_event_at=now - timedelta(seconds=20),
        now=now,
    )
    assert not stale.allowed
    assert stale.stale_feed
    assert stale.reconnect_allowed
    assert stale.recommendation == "RECONNECT"

    governance = AutomaticReconnectionGovernance(policy)
    decision = governance.evaluate(stale, now=now)
    assert decision.allowed
    assert decision.action == "RECONNECT"

    cooldown = governance.evaluate(stale, now=now + timedelta(seconds=1))
    assert not cooldown.allowed
    assert "RECONNECT_COOLDOWN_ACTIVE" in cooldown.rejection_reasons

    closed_stale = monitor.evaluate(
        provider_service.lifecycle.profile,
        holiday,
        last_event_at=now - timedelta(seconds=20),
        now=now,
    )
    closed_decision = governance.evaluate(
        closed_stale,
        now=now + timedelta(seconds=10),
    )
    assert not closed_decision.allowed
    assert "MARKET_CLOSED" in closed_decision.rejection_reasons

    print(
        "All market-hours, stale-feed monitoring and automatic "
        "reconnection-governance assertions passed."
    )


if __name__ == "__main__":
    main()
