from __future__ import annotations
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any

def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

@dataclass(frozen=True)
class RetryAttempt:
    attempt_number: int
    started_at: str
    completed_at: str
    succeeded: bool
    delay_before_attempt_seconds: float
    exception_type: str | None = None
    exception_message: str | None = None
    status: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

@dataclass(frozen=True)
class RetryExecutionResult:
    operation_id: str
    dependency_name: str
    succeeded: bool
    exhausted: bool
    attempt_count: int
    total_delay_seconds: float
    value: Any = None
    attempts: tuple[RetryAttempt, ...] = ()
    final_exception_type: str | None = None
    final_exception_message: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

@dataclass(frozen=True)
class CircuitBreakerState:
    circuit_id: str
    dependency_name: str
    state: str = "CLOSED"
    failure_count: int = 0
    success_count: int = 0
    half_open_calls: int = 0
    opened_at: str | None = None
    last_failure_at: str | None = None
    last_success_at: str | None = None
    version: int = 1
    updated_at: str = field(default_factory=utc_now_iso)
    metadata: dict[str, Any] = field(default_factory=dict)

@dataclass(frozen=True)
class BulkheadState:
    bulkhead_id: str
    dependency_name: str
    active_calls: int = 0
    queued_calls: int = 0
    rejected_calls: int = 0
    completed_calls: int = 0
    version: int = 1
    updated_at: str = field(default_factory=utc_now_iso)
    metadata: dict[str, Any] = field(default_factory=dict)

@dataclass(frozen=True)
class ResilienceExecutionDecision:
    valid: bool
    allowed: bool
    operation_id: str
    dependency_name: str
    recommendation: str
    retry_result: RetryExecutionResult | None = None
    circuit_state: CircuitBreakerState | None = None
    bulkhead_state: BulkheadState | None = None
    warnings: tuple[str, ...] = ()
    rejection_reasons: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)
    evaluated_at: str = field(default_factory=utc_now_iso)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
