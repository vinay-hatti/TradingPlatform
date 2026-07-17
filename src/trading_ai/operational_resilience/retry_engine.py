from __future__ import annotations
from datetime import datetime, timezone
import hashlib
from typing import Any, Callable

from .resilience_policy import RetryPolicy
from .resilience_profile import RetryAttempt, RetryExecutionResult

class RetryEngine:
    def __init__(self, policy: RetryPolicy | None = None) -> None:
        self.policy = policy or RetryPolicy()
        self.policy.validate()

    def delay_for(self, operation_id: str, attempt_number: int) -> float:
        base = min(
            self.policy.maximum_delay_seconds,
            self.policy.initial_delay_seconds
            * (self.policy.backoff_multiplier ** max(0, attempt_number - 1)),
        )
        if base == 0 or self.policy.jitter_ratio == 0:
            return round(base, 6)
        digest = hashlib.sha256(
            f"{operation_id}:{attempt_number}".encode("utf-8")
        ).digest()
        unit = int.from_bytes(digest[:8], "big") / float(2**64 - 1)
        jitter = (unit * 2.0 - 1.0) * self.policy.jitter_ratio
        return round(max(0.0, base * (1.0 + jitter)), 6)

    def is_retryable_exception(self, exc: BaseException) -> bool:
        return type(exc).__name__ in self.policy.retryable_exceptions

    def execute(
        self,
        *,
        operation_id: str,
        dependency_name: str,
        operation: Callable[[], Any],
        sleeper: Callable[[float], None] | None = None,
    ) -> RetryExecutionResult:
        sleeper = sleeper or (lambda _: None)
        attempts = []
        total_delay = 0.0
        final_exc = None

        for attempt_number in range(1, self.policy.maximum_attempts + 1):
            delay = 0.0 if attempt_number == 1 else self.delay_for(
                operation_id, attempt_number - 1
            )
            if delay:
                sleeper(delay)
                total_delay += delay
            started = datetime.now(timezone.utc).isoformat()
            try:
                value = operation()
                completed = datetime.now(timezone.utc).isoformat()
                attempts.append(RetryAttempt(
                    attempt_number=attempt_number,
                    started_at=started,
                    completed_at=completed,
                    succeeded=True,
                    delay_before_attempt_seconds=delay,
                    status="SUCCESS",
                ))
                return RetryExecutionResult(
                    operation_id=operation_id,
                    dependency_name=dependency_name,
                    succeeded=True,
                    exhausted=False,
                    attempt_count=attempt_number,
                    total_delay_seconds=round(total_delay, 6),
                    value=value,
                    attempts=tuple(attempts),
                )
            except BaseException as exc:
                final_exc = exc
                completed = datetime.now(timezone.utc).isoformat()
                retryable = self.is_retryable_exception(exc)
                attempts.append(RetryAttempt(
                    attempt_number=attempt_number,
                    started_at=started,
                    completed_at=completed,
                    succeeded=False,
                    delay_before_attempt_seconds=delay,
                    exception_type=type(exc).__name__,
                    exception_message=str(exc),
                    status="RETRYABLE_FAILURE" if retryable else "TERMINAL_FAILURE",
                ))
                if not retryable:
                    break

        return RetryExecutionResult(
            operation_id=operation_id,
            dependency_name=dependency_name,
            succeeded=False,
            exhausted=len(attempts) >= self.policy.maximum_attempts,
            attempt_count=len(attempts),
            total_delay_seconds=round(total_delay, 6),
            attempts=tuple(attempts),
            final_exception_type=(
                type(final_exc).__name__ if final_exc is not None else None
            ),
            final_exception_message=(
                str(final_exc) if final_exc is not None else None
            ),
        )
