from __future__ import annotations
from typing import Any, Callable

from .circuit_breaker_engine import CircuitBreakerEngine
from .failure_isolation_engine import FailureIsolationEngine
from .resilience_policy import OperationalResiliencePolicy
from .resilience_profile import ResilienceExecutionDecision
from .resilience_state_repository import JsonResilienceStateRepository
from .retry_engine import RetryEngine

class ResilienceExecutionService:
    def __init__(
        self,
        *,
        policy: OperationalResiliencePolicy | None = None,
        repository: JsonResilienceStateRepository | None = None,
    ) -> None:
        self.policy = policy or OperationalResiliencePolicy()
        self.policy.validate()
        self.repository = repository or JsonResilienceStateRepository()
        self.retry_engine = RetryEngine(self.policy.retry)
        self.circuit_engine = CircuitBreakerEngine(
            self.policy.circuit_breaker
        )
        self.isolation_engine = FailureIsolationEngine(
            self.policy.isolation
        )

    def execute(
        self,
        *,
        operation_id: str,
        dependency_name: str,
        operation: Callable[[], Any],
        sleeper: Callable[[float], None] | None = None,
    ) -> ResilienceExecutionDecision:
        circuit = self.repository.circuit(dependency_name)
        permitted, circuit = self.circuit_engine.permit(circuit)
        self.repository.save_circuit(circuit)
        if not permitted:
            return ResilienceExecutionDecision(
                valid=True,
                allowed=False,
                operation_id=operation_id,
                dependency_name=dependency_name,
                recommendation="REJECT_OPEN_CIRCUIT",
                circuit_state=circuit,
                rejection_reasons=("CIRCUIT_OPEN",),
            )

        bulkhead = self.repository.bulkhead(dependency_name)
        acquired, bulkhead = self.isolation_engine.acquire(bulkhead)
        self.repository.save_bulkhead(bulkhead)
        if not acquired:
            return ResilienceExecutionDecision(
                valid=True,
                allowed=False,
                operation_id=operation_id,
                dependency_name=dependency_name,
                recommendation="REJECT_BULKHEAD_SATURATED",
                circuit_state=circuit,
                bulkhead_state=bulkhead,
                rejection_reasons=("BULKHEAD_SATURATED",),
            )

        retry_result = self.retry_engine.execute(
            operation_id=operation_id,
            dependency_name=dependency_name,
            operation=operation,
            sleeper=sleeper,
        )
        bulkhead = self.isolation_engine.release(bulkhead)
        self.repository.save_bulkhead(bulkhead)

        if retry_result.succeeded:
            circuit = self.circuit_engine.record_success(circuit)
            recommendation = "SUCCESS"
            allowed = True
            rejections = ()
        else:
            circuit = self.circuit_engine.record_failure(circuit)
            recommendation = (
                "OPEN_CIRCUIT"
                if circuit.state == "OPEN"
                else "RETRY_EXHAUSTED"
            )
            allowed = False
            rejections = (
                "RETRY_EXHAUSTED"
                if retry_result.exhausted
                else "TERMINAL_FAILURE",
            )
        self.repository.save_circuit(circuit)

        return ResilienceExecutionDecision(
            valid=True,
            allowed=allowed,
            operation_id=operation_id,
            dependency_name=dependency_name,
            recommendation=recommendation,
            retry_result=retry_result,
            circuit_state=circuit,
            bulkhead_state=bulkhead,
            rejection_reasons=rejections,
            metadata={
                "attempt_count": retry_result.attempt_count,
                "total_delay_seconds": retry_result.total_delay_seconds,
            },
        )
