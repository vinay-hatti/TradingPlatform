from __future__ import annotations
from datetime import datetime, timedelta, timezone
import tempfile
from pathlib import Path

from trading_ai.operational_resilience.circuit_breaker_engine import (
    CircuitBreakerEngine,
)
from trading_ai.operational_resilience.failure_isolation_engine import (
    FailureIsolationEngine,
)
from trading_ai.operational_resilience.resilience_execution_service import (
    ResilienceExecutionService,
)
from trading_ai.operational_resilience.resilience_policy import (
    CircuitBreakerPolicy,
    FailureIsolationPolicy,
    OperationalResiliencePolicy,
    RetryPolicy,
)
from trading_ai.operational_resilience.resilience_profile import (
    BulkheadState,
    CircuitBreakerState,
)
from trading_ai.operational_resilience.resilience_serialization import dumps
from trading_ai.operational_resilience.resilience_state_repository import (
    JsonResilienceStateRepository,
)
from trading_ai.operational_resilience.retry_engine import RetryEngine

def main() -> None:
    retry = RetryEngine(RetryPolicy(
        maximum_attempts=4,
        initial_delay_seconds=1.0,
        maximum_delay_seconds=10.0,
        backoff_multiplier=2.0,
        jitter_ratio=0.0,
    ))
    assert retry.delay_for("op-1", 1) == 1.0
    assert retry.delay_for("op-1", 2) == 2.0
    assert retry.delay_for("op-1", 3) == 4.0

    attempts = {"count": 0}
    sleeps = []
    def flaky():
        attempts["count"] += 1
        if attempts["count"] < 3:
            raise TimeoutError("temporary")
        return "ok"

    result = retry.execute(
        operation_id="op-flaky",
        dependency_name="market-provider",
        operation=flaky,
        sleeper=sleeps.append,
    )
    assert result.succeeded
    assert result.attempt_count == 3
    assert sleeps == [1.0, 2.0]
    assert result.total_delay_seconds == 3.0
    assert result.value == "ok"

    circuit_policy = CircuitBreakerPolicy(
        failure_threshold=2,
        success_threshold=1,
        recovery_timeout_seconds=10.0,
    )
    circuit_engine = CircuitBreakerEngine(circuit_policy)
    now = datetime.now(timezone.utc)
    circuit = CircuitBreakerState(
        circuit_id="circuit:test",
        dependency_name="test",
    )
    circuit = circuit_engine.record_failure(circuit, as_of=now)
    assert circuit.state == "CLOSED"
    circuit = circuit_engine.record_failure(circuit, as_of=now)
    assert circuit.state == "OPEN"
    permitted, same = circuit_engine.permit(
        circuit,
        as_of=now + timedelta(seconds=5),
    )
    assert not permitted
    assert same.state == "OPEN"
    permitted, half_open = circuit_engine.permit(
        circuit,
        as_of=now + timedelta(seconds=11),
    )
    assert permitted
    assert half_open.state == "HALF_OPEN"
    closed = circuit_engine.record_success(
        half_open,
        as_of=now + timedelta(seconds=12),
    )
    assert closed.state == "CLOSED"

    isolation = FailureIsolationEngine(FailureIsolationPolicy(
        maximum_concurrent_calls=1,
        maximum_queue_depth=0,
        reject_when_saturated=True,
    ))
    bulkhead = BulkheadState(
        bulkhead_id="bulkhead:test",
        dependency_name="test",
    )
    acquired, bulkhead = isolation.acquire(bulkhead)
    assert acquired
    acquired_again, saturated = isolation.acquire(bulkhead)
    assert not acquired_again
    assert saturated.rejected_calls == 1
    released = isolation.release(bulkhead)
    assert released.active_calls == 0
    assert released.completed_calls == 1

    with tempfile.TemporaryDirectory() as temp:
        repository = JsonResilienceStateRepository(
            Path(temp) / "resilience.json"
        )
        service = ResilienceExecutionService(
            policy=OperationalResiliencePolicy(
                retry=RetryPolicy(
                    maximum_attempts=2,
                    initial_delay_seconds=0.0,
                    maximum_delay_seconds=0.0,
                    jitter_ratio=0.0,
                ),
                circuit_breaker=CircuitBreakerPolicy(
                    failure_threshold=2,
                    success_threshold=1,
                    recovery_timeout_seconds=1.0,
                ),
                isolation=FailureIsolationPolicy(
                    maximum_concurrent_calls=2,
                ),
            ),
            repository=repository,
        )

        success = service.execute(
            operation_id="success-1",
            dependency_name="database",
            operation=lambda: {"rows": 1},
        )
        assert success.allowed
        assert success.recommendation == "SUCCESS"
        assert success.retry_result is not None
        assert success.retry_result.value == {"rows": 1}
        assert success.circuit_state is not None
        assert success.circuit_state.state == "CLOSED"

        failure_one = service.execute(
            operation_id="failure-1",
            dependency_name="broker",
            operation=lambda: (_ for _ in ()).throw(
                TimeoutError("broker timeout")
            ),
        )
        assert not failure_one.allowed
        assert failure_one.retry_result is not None
        assert failure_one.retry_result.exhausted
        assert failure_one.circuit_state is not None
        assert failure_one.circuit_state.state == "CLOSED"

        failure_two = service.execute(
            operation_id="failure-2",
            dependency_name="broker",
            operation=lambda: (_ for _ in ()).throw(
                TimeoutError("broker timeout")
            ),
        )
        assert not failure_two.allowed
        assert failure_two.recommendation == "OPEN_CIRCUIT"
        assert failure_two.circuit_state is not None
        assert failure_two.circuit_state.state == "OPEN"

        blocked = service.execute(
            operation_id="blocked",
            dependency_name="broker",
            operation=lambda: "should-not-run",
        )
        assert not blocked.allowed
        assert blocked.recommendation == "REJECT_OPEN_CIRCUIT"
        assert "CIRCUIT_OPEN" in blocked.rejection_reasons

        persisted = repository.circuit("broker")
        assert persisted.state == "OPEN"
        persisted_bulkhead = repository.bulkhead("database")
        assert persisted_bulkhead.completed_calls == 1

        payload = dumps(success)
        assert '"recommendation": "SUCCESS"' in payload
        assert '"dependency_name": "database"' in payload

    print(
        "All retry, exponential-backoff, circuit-breaker, and "
        "failure-isolation assertions passed."
    )

if __name__ == "__main__":
    main()
