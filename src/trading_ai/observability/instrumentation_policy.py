from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class OperationInstrumentationPolicy:
    record_duration_histogram: bool = True
    record_success_counter: bool = True
    record_failure_counter: bool = True
    emit_start_log: bool = True
    emit_completion_log: bool = True
    emit_failure_log: bool = True
    create_child_span: bool = True
    include_exception_details: bool = True
    metric_prefix: str = "trading_ai"

    def validate(self) -> None:
        if not self.metric_prefix:
            raise ValueError("metric_prefix cannot be empty")


@dataclass(frozen=True)
class RuntimeMetricsCollectionPolicy:
    collect_process_uptime: bool = True
    collect_health_score: bool = True
    collect_service_readiness: bool = True
    collect_circuit_state: bool = True
    collect_bulkhead_state: bool = True
    collect_recovery_state: bool = True
    collect_incident_state: bool = True
    collect_watchdog_state: bool = True
    persist_samples: bool = True


@dataclass(frozen=True)
class TracePropagationPolicy:
    trace_header: str = "traceparent"
    baggage_header: str = "baggage"
    correlation_header: str = "x-correlation-id"
    request_header: str = "x-request-id"
    require_valid_traceparent: bool = True
    propagate_baggage: bool = True

    def validate(self) -> None:
        if not self.trace_header:
            raise ValueError("trace_header cannot be empty")
        if not self.correlation_header:
            raise ValueError("correlation_header cannot be empty")


@dataclass(frozen=True)
class ObservabilityInstrumentationPolicy:
    operation: OperationInstrumentationPolicy = (
        OperationInstrumentationPolicy()
    )
    runtime: RuntimeMetricsCollectionPolicy = (
        RuntimeMetricsCollectionPolicy()
    )
    propagation: TracePropagationPolicy = TracePropagationPolicy()

    def validate(self) -> None:
        self.operation.validate()
        self.propagation.validate()
