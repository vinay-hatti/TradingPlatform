from __future__ import annotations
from dataclasses import replace
from datetime import datetime, timezone

from .resilience_policy import FailureIsolationPolicy
from .resilience_profile import BulkheadState

class FailureIsolationEngine:
    def __init__(
        self,
        policy: FailureIsolationPolicy | None = None,
    ) -> None:
        self.policy = policy or FailureIsolationPolicy()
        self.policy.validate()

    def acquire(
        self,
        state: BulkheadState,
    ) -> tuple[bool, BulkheadState]:
        now = datetime.now(timezone.utc).isoformat()
        if state.active_calls < self.policy.maximum_concurrent_calls:
            return True, replace(
                state,
                active_calls=state.active_calls + 1,
                version=state.version + 1,
                updated_at=now,
            )
        if (
            not self.policy.reject_when_saturated
            and state.queued_calls < self.policy.maximum_queue_depth
        ):
            return False, replace(
                state,
                queued_calls=state.queued_calls + 1,
                version=state.version + 1,
                updated_at=now,
            )
        return False, replace(
            state,
            rejected_calls=state.rejected_calls + 1,
            version=state.version + 1,
            updated_at=now,
        )

    def release(
        self,
        state: BulkheadState,
    ) -> BulkheadState:
        now = datetime.now(timezone.utc).isoformat()
        return replace(
            state,
            active_calls=max(0, state.active_calls - 1),
            completed_calls=state.completed_calls + 1,
            version=state.version + 1,
            updated_at=now,
        )
