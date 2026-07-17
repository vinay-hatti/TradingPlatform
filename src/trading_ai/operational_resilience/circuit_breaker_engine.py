from __future__ import annotations
from dataclasses import replace
from datetime import datetime, timezone

from .resilience_policy import CircuitBreakerPolicy
from .resilience_profile import CircuitBreakerState

def _parse(value: str | None) -> datetime | None:
    if value is None:
        return None
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)

class CircuitBreakerEngine:
    def __init__(
        self,
        policy: CircuitBreakerPolicy | None = None,
    ) -> None:
        self.policy = policy or CircuitBreakerPolicy()
        self.policy.validate()

    def permit(
        self,
        state: CircuitBreakerState,
        *,
        as_of: datetime | None = None,
    ) -> tuple[bool, CircuitBreakerState]:
        now = as_of or datetime.now(timezone.utc)
        if state.state == "CLOSED":
            return True, state
        if state.state == "OPEN":
            opened = _parse(state.opened_at)
            if opened and (
                now - opened
            ).total_seconds() >= self.policy.recovery_timeout_seconds:
                updated = replace(
                    state,
                    state="HALF_OPEN",
                    success_count=0,
                    half_open_calls=0,
                    version=state.version + 1,
                    updated_at=now.isoformat(),
                )
                return True, updated
            return False, state
        if state.state == "HALF_OPEN":
            return (
                state.half_open_calls < self.policy.half_open_max_calls,
                state,
            )
        return False, state

    def record_success(
        self,
        state: CircuitBreakerState,
        *,
        as_of: datetime | None = None,
    ) -> CircuitBreakerState:
        now = as_of or datetime.now(timezone.utc)
        if state.state == "HALF_OPEN":
            successes = state.success_count + 1
            if successes >= self.policy.success_threshold:
                return replace(
                    state,
                    state="CLOSED",
                    failure_count=0,
                    success_count=0,
                    half_open_calls=0,
                    opened_at=None,
                    last_success_at=now.isoformat(),
                    version=state.version + 1,
                    updated_at=now.isoformat(),
                )
            return replace(
                state,
                success_count=successes,
                half_open_calls=state.half_open_calls + 1,
                last_success_at=now.isoformat(),
                version=state.version + 1,
                updated_at=now.isoformat(),
            )
        return replace(
            state,
            failure_count=0,
            last_success_at=now.isoformat(),
            version=state.version + 1,
            updated_at=now.isoformat(),
        )

    def record_failure(
        self,
        state: CircuitBreakerState,
        *,
        as_of: datetime | None = None,
    ) -> CircuitBreakerState:
        now = as_of or datetime.now(timezone.utc)
        failures = state.failure_count + 1
        should_open = (
            state.state == "HALF_OPEN"
            or failures >= self.policy.failure_threshold
        )
        return replace(
            state,
            state="OPEN" if should_open else state.state,
            failure_count=failures,
            success_count=0,
            half_open_calls=0,
            opened_at=now.isoformat() if should_open else state.opened_at,
            last_failure_at=now.isoformat(),
            version=state.version + 1,
            updated_at=now.isoformat(),
        )
