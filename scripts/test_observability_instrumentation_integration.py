from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import tempfile

from trading_ai.observability.instrumented_observability_service import (
    InstrumentedObservabilityService,
)
from trading_ai.observability.observability_profile import (
    ObservabilityContext,
)
from trading_ai.operational_resilience.resilience_profile import (
    BulkheadState,
    CircuitBreakerState,
    ResilienceExecutionDecision,
)
from trading_ai.operational_resilience.recovery_profile import (
    IncidentRecord,
    RecoveryDecision,
    RecoveryWorkflowState,
)
from trading_ai.operational_resilience.service_health_engine import (
    ServiceHealthEngine,
)
from trading_ai.operational_resilience.service_health_profile import (
    DependencyHealth,
    ServiceHeartbeat,
)
from trading_ai.operational_resilience.watchdog_profile import (
    WatchdogCycleState,
    WatchdogDecision,
)


def main() -> None:
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        service = InstrumentedObservabilityService(
            metrics_path=root / "metrics.json",
            traces_path=root / "traces.json",
        )

        context = ObservabilityContext(
            service_name="order-management",
            environment="paper",
            instance_id="oms-1",
            operation="submit_order",
            correlation_id="corr-100",
            request_id="req-100",
        )
        result = service.operations.execute(
            operation=lambda: {"order_id": "O-100"},
            context=context,
            span_name="submit_order",
            span_kind="SERVER",
            attributes={"order.type": "LIMIT"},
        )
        assert result == {"order_id": "O-100"}

        try:
            service.operations.execute(
                operation=lambda: (_ for _ in ()).throw(
                    TimeoutError("broker timeout")
                ),
                context=context,
                span_name="submit_order_failed",
            )
            raise AssertionError("Expected TimeoutError")
        except TimeoutError:
            pass

        operation_samples = service.observability.metrics.samples(
            "trading_ai_operations_total"
        )
        statuses = {sample.labels["status"] for sample in operation_samples}
        assert statuses == {"success", "failure"}
        durations = service.observability.metrics.samples(
            "trading_ai_operation_duration_seconds"
        )
        assert len(durations) == 2
        assert all(sample.exemplar_trace_id for sample in durations)

        parent = service.observability.tracing.start_span(
            name="gateway_request",
            service_name="api-gateway",
            environment="paper",
            kind="SERVER",
            baggage={"desk": "systematic"},
        )
        headers = service.propagation.inject(
            span=parent,
            context=context,
        )
        extracted = service.propagation.extract(headers)
        assert extracted.trace_id == parent.trace_id
        assert extracted.parent_span_id == parent.span_id
        assert extracted.sampled
        assert extracted.baggage["desk"] == "systematic"
        assert extracted.correlation_id == "corr-100"
        assert extracted.request_id == "req-100"
        service.observability.tracing.end_span(parent)

        now = datetime.now(timezone.utc)
        health = ServiceHealthEngine().evaluate(
            registry_id="paper-runtime",
            environment="paper",
            heartbeats=(
                ServiceHeartbeat(
                    service_name="market-data",
                    instance_id="md-1",
                    environment="paper",
                    status="RUNNING",
                    timestamp=now.isoformat(),
                    critical=True,
                ),
            ),
            dependencies_by_service={
                "market-data": (
                    DependencyHealth(
                        dependency_name="postgresql",
                        dependency_type="DATABASE",
                        status="UP",
                        checked_at=now.isoformat(),
                        critical=True,
                    ),
                )
            },
            as_of=now,
        )
        service.operational_resilience.observe_runtime_health(health)
        assert service.observability.metrics.samples(
            "trading_ai_runtime_health_score"
        )
        assert service.observability.metrics.samples(
            "trading_ai_service_ready"
        )

        resilience = ResilienceExecutionDecision(
            valid=True,
            allowed=False,
            operation_id="broker-op-1",
            dependency_name="broker",
            recommendation="REJECT_OPEN_CIRCUIT",
            circuit_state=CircuitBreakerState(
                circuit_id="circuit:broker",
                dependency_name="broker",
                state="OPEN",
            ),
            bulkhead_state=BulkheadState(
                bulkhead_id="bulkhead:broker",
                dependency_name="broker",
                active_calls=2,
            ),
            rejection_reasons=("CIRCUIT_OPEN",),
        )
        service.operational_resilience.observe_resilience_execution(
            resilience
        )
        circuit_sample = service.observability.metrics.samples(
            "trading_ai_circuit_open"
        )[-1]
        assert circuit_sample.value == 1.0
        bulkhead_sample = service.observability.metrics.samples(
            "trading_ai_bulkhead_active_calls"
        )[-1]
        assert bulkhead_sample.value == 2.0

        incident = IncidentRecord(
            incident_id="incident-1",
            title="Broker recovery failed",
            service_name="broker-adapter",
            environment="paper",
            severity="CRITICAL",
        )
        recovery_state = RecoveryWorkflowState(
            workflow_id="recovery-1",
            service_name="broker-adapter",
            instance_id="broker-1",
            environment="paper",
            trigger="watchdog-health-failure",
            status="FAILED",
            current_step="INCIDENT_OPENED",
            attempt_count=3,
            incident=incident,
        )
        recovery = RecoveryDecision(
            valid=True,
            allowed=False,
            workflow_id="recovery-1",
            service_name="broker-adapter",
            recommendation="INCIDENT_OPENED",
            state=recovery_state,
            incident=incident,
        )
        service.operational_resilience.observe_recovery(recovery)
        assert service.observability.metrics.samples(
            "trading_ai_recovery_workflows_total"
        )
        assert service.observability.metrics.samples(
            "trading_ai_incidents_total"
        )

        cycle = WatchdogCycleState(
            cycle_id="watchdog-1",
            environment="paper",
            sequence_number=1,
            status="COMPLETED",
            recommendation="RECOVERY_REQUIRED",
            alert_count=1,
            incident_count=1,
            recovery_count=1,
        )
        watchdog = WatchdogDecision(
            valid=True,
            allowed=False,
            environment="paper",
            cycle_id="watchdog-1",
            recommendation="RECOVERY_REQUIRED",
            cycle_state=cycle,
        )
        service.operational_resilience.observe_watchdog(watchdog)
        assert service.observability.metrics.samples(
            "trading_ai_watchdog_cycles_total"
        )

        service.runtime_metrics.collect_uptime(
            environment="paper",
            service="trading-ai",
        )
        assert service.observability.metrics.samples(
            "trading_ai_runtime_uptime_seconds"
        )

        assert (root / "metrics.json").exists()
        assert (root / "traces.json").exists()

    print(
        "All observability instrumentation, runtime metrics, trace "
        "propagation, and operational-resilience integration assertions passed."
    )


if __name__ == "__main__":
    main()
