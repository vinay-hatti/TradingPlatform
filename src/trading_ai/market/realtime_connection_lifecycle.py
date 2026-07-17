from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone

from .realtime_provider_policy import RealTimeProviderPolicy
from .realtime_provider_profile import ProviderConnectionProfile


class ProviderConnectionLifecycle:
    STATES = (
        "DISCONNECTED",
        "CONNECTING",
        "CONNECTED",
        "DEGRADED",
        "RECONNECTING",
        "FAILED",
        "STOPPED",
    )

    def __init__(
        self,
        provider: str,
        policy: RealTimeProviderPolicy | None = None,
    ) -> None:
        self.provider = provider.strip().lower()
        self.policy = policy or RealTimeProviderPolicy()
        self.policy.validate()
        self.profile = ProviderConnectionProfile(
            provider=self.provider,
            state="DISCONNECTED",
            connected=False,
            score=0.0,
            grade="F",
            severity="CRITICAL",
            allowed=False,
            recommendation="CONNECT",
        )

    @staticmethod
    def _grade(score: float) -> tuple[str, str]:
        if score >= 95:
            return "A", "LOW"
        if score >= 85:
            return "B", "MODERATE"
        if score >= 70:
            return "C", "SEVERE"
        return "F", "CRITICAL"

    def _set(
        self,
        *,
        state: str,
        connected: bool,
        score: float,
        recommendation: str,
        connection_id: str | None = None,
        warnings: tuple[str, ...] = (),
        rejection_reasons: tuple[str, ...] = (),
    ) -> ProviderConnectionProfile:
        grade, severity = self._grade(score)
        now = datetime.now(timezone.utc).isoformat()
        self.profile = replace(
            self.profile,
            state=state,
            connected=connected,
            connection_id=connection_id if connection_id is not None else self.profile.connection_id,
            connected_at=now if state == "CONNECTED" else self.profile.connected_at,
            disconnected_at=now if state in {"DISCONNECTED", "FAILED", "STOPPED"} else self.profile.disconnected_at,
            score=score,
            grade=grade,
            severity=severity,
            allowed=connected and not rejection_reasons,
            recommendation=recommendation,
            warnings=warnings,
            rejection_reasons=rejection_reasons,
        )
        return self.profile

    def connecting(self) -> ProviderConnectionProfile:
        return self._set(state="CONNECTING", connected=False, score=40.0, recommendation="WAIT")

    def connected(self, connection_id: str) -> ProviderConnectionProfile:
        self.profile = replace(self.profile, reconnect_attempts=0, next_reconnect_delay_seconds=0.0)
        return self._set(
            state="CONNECTED",
            connected=True,
            score=100.0,
            recommendation="STREAM",
            connection_id=connection_id,
        )

    def heartbeat(self) -> ProviderConnectionProfile:
        now = datetime.now(timezone.utc).isoformat()
        self.profile = replace(self.profile, last_heartbeat_at=now)
        return self.profile

    def degraded(self, warning: str) -> ProviderConnectionProfile:
        return self._set(
            state="DEGRADED",
            connected=True,
            score=75.0,
            recommendation="MONITOR",
            warnings=(warning,),
        )

    def disconnected(self, reason: str = "DISCONNECTED") -> ProviderConnectionProfile:
        return self._set(
            state="DISCONNECTED",
            connected=False,
            score=0.0,
            recommendation="RECONNECT",
            rejection_reasons=(reason,),
        )

    def reconnecting(self) -> ProviderConnectionProfile:
        attempts = self.profile.reconnect_attempts + 1
        delay = min(
            self.policy.reconnect_initial_delay_seconds
            * (self.policy.reconnect_multiplier ** max(0, attempts - 1)),
            self.policy.reconnect_max_delay_seconds,
        )
        if attempts > self.policy.maximum_reconnect_attempts:
            self.profile = replace(
                self.profile,
                reconnect_attempts=attempts,
                next_reconnect_delay_seconds=delay,
            )
            return self._set(
                state="FAILED",
                connected=False,
                score=0.0,
                recommendation="STOP",
                rejection_reasons=("MAXIMUM_RECONNECT_ATTEMPTS_EXCEEDED",),
            )
        self.profile = replace(
            self.profile,
            reconnect_attempts=attempts,
            next_reconnect_delay_seconds=delay,
        )
        return self._set(
            state="RECONNECTING",
            connected=False,
            score=30.0,
            recommendation="RETRY",
        )

    def stopped(self) -> ProviderConnectionProfile:
        return self._set(state="STOPPED", connected=False, score=0.0, recommendation="STOP")
