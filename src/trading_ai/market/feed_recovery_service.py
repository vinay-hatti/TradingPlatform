from __future__ import annotations

from datetime import datetime
from typing import Any

from .feed_monitor_policy import FeedMonitorPolicy
from .feed_monitor_profile import FeedHealthProfile, ReconnectionDecisionProfile
from .market_hours_service import MarketHoursService
from .reconnection_governance import AutomaticReconnectionGovernance
from .realtime_provider_service import RealTimeProviderService
from .stale_feed_monitor import StaleFeedMonitor


class FeedRecoveryService:
    def __init__(
        self,
        provider_service: RealTimeProviderService,
        *,
        market_hours_service: MarketHoursService | None = None,
        policy: FeedMonitorPolicy | None = None,
    ) -> None:
        self.provider_service = provider_service
        self.market_hours_service = market_hours_service or MarketHoursService()
        self.policy = policy or FeedMonitorPolicy()
        self.monitor = StaleFeedMonitor(self.policy)
        self.governance = AutomaticReconnectionGovernance(self.policy)

    def evaluate(
        self,
        *,
        last_event_at: str | datetime | None = None,
        now: datetime | None = None,
    ) -> tuple[FeedHealthProfile, ReconnectionDecisionProfile | None]:
        session = self.market_hours_service.evaluate(now)
        health = self.monitor.evaluate(
            self.provider_service.lifecycle.profile,
            session,
            last_event_at=last_event_at,
            now=now,
        )
        decision = None
        if health.recommendation == "RECONNECT":
            decision = self.governance.evaluate(health, now=now)
        return health, decision

    def recover(
        self,
        *,
        last_event_at: str | datetime | None = None,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        health, decision = self.evaluate(last_event_at=last_event_at, now=now)
        result = None
        if decision is not None and decision.allowed:
            result = self.provider_service.reconnect()
        return {
            "health": health,
            "decision": decision,
            "result": result,
        }
