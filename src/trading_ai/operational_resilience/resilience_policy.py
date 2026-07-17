from __future__ import annotations
from dataclasses import dataclass

@dataclass(frozen=True)
class RetryPolicy:
    maximum_attempts: int = 4
    initial_delay_seconds: float = 0.25
    maximum_delay_seconds: float = 30.0
    backoff_multiplier: float = 2.0
    jitter_ratio: float = 0.10
    retryable_exceptions: tuple[str, ...] = (
        "TimeoutError", "ConnectionError", "OSError",
    )
    retryable_statuses: tuple[str, ...] = (
        "TIMEOUT", "UNAVAILABLE", "THROTTLED", "TRANSIENT_FAILURE",
    )

    def validate(self) -> None:
        if self.maximum_attempts <= 0:
            raise ValueError("maximum_attempts must be positive")
        if self.initial_delay_seconds < 0:
            raise ValueError("initial_delay_seconds cannot be negative")
        if self.maximum_delay_seconds < self.initial_delay_seconds:
            raise ValueError("maximum_delay_seconds cannot be below initial delay")
        if self.backoff_multiplier < 1:
            raise ValueError("backoff_multiplier must be at least 1")
        if not 0 <= self.jitter_ratio <= 1:
            raise ValueError("jitter_ratio must be in [0, 1]")

@dataclass(frozen=True)
class CircuitBreakerPolicy:
    failure_threshold: int = 5
    success_threshold: int = 2
    recovery_timeout_seconds: float = 30.0
    rolling_window_seconds: float = 60.0
    half_open_max_calls: int = 1
    count_retry_exhaustion_as_failure: bool = True

    def validate(self) -> None:
        if self.failure_threshold <= 0:
            raise ValueError("failure_threshold must be positive")
        if self.success_threshold <= 0:
            raise ValueError("success_threshold must be positive")
        if self.recovery_timeout_seconds <= 0:
            raise ValueError("recovery_timeout_seconds must be positive")
        if self.rolling_window_seconds <= 0:
            raise ValueError("rolling_window_seconds must be positive")
        if self.half_open_max_calls <= 0:
            raise ValueError("half_open_max_calls must be positive")

@dataclass(frozen=True)
class FailureIsolationPolicy:
    maximum_concurrent_calls: int = 10
    maximum_queue_depth: int = 100
    queue_timeout_seconds: float = 5.0
    reject_when_saturated: bool = True
    isolate_by_dependency: bool = True
    persist_state: bool = True
    fail_closed: bool = True

    def validate(self) -> None:
        if self.maximum_concurrent_calls <= 0:
            raise ValueError("maximum_concurrent_calls must be positive")
        if self.maximum_queue_depth < 0:
            raise ValueError("maximum_queue_depth cannot be negative")
        if self.queue_timeout_seconds < 0:
            raise ValueError("queue_timeout_seconds cannot be negative")

@dataclass(frozen=True)
class OperationalResiliencePolicy:
    retry: RetryPolicy = RetryPolicy()
    circuit_breaker: CircuitBreakerPolicy = CircuitBreakerPolicy()
    isolation: FailureIsolationPolicy = FailureIsolationPolicy()

    def validate(self) -> None:
        self.retry.validate()
        self.circuit_breaker.validate()
        self.isolation.validate()
