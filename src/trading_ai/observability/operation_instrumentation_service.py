from __future__ import annotations

from dataclasses import replace
from time import perf_counter
from typing import Any, Callable

from .instrumentation_policy import OperationInstrumentationPolicy
from .observability_profile import (
    MetricDefinition,
    ObservabilityContext,
    TraceSpan,
)
from .observability_service import ObservabilityService


class OperationInstrumentationService:
    def __init__(
        self,
        *,
        observability: ObservabilityService,
        policy: OperationInstrumentationPolicy | None = None,
    ) -> None:
        self.observability = observability
        self.policy = policy or OperationInstrumentationPolicy()
        self.policy.validate()
        self._register_metrics()

    def _register_metrics(self) -> None:
        labels = ("environment", "service", "operation")
        definitions = (
            MetricDefinition(
                name=f"{self.policy.metric_prefix}_operations_total",
                metric_type="COUNTER",
                description="Instrumented operation outcomes.",
                unit="operations",
                label_names=labels + ("status",),
            ),
            MetricDefinition(
                name=(
                    f"{self.policy.metric_prefix}_operation_duration_seconds"
                ),
                metric_type="HISTOGRAM",
                description="Instrumented operation duration.",
                unit="seconds",
                label_names=labels,
            ),
        )
        for definition in definitions:
            try:
                self.observability.metrics.register(definition)
            except ValueError:
                pass

    def execute(
        self,
        *,
        operation: Callable[[], Any],
        context: ObservabilityContext,
        span_name: str | None = None,
        parent_span: TraceSpan | None = None,
        span_kind: str = "INTERNAL",
        attributes: dict[str, Any] | None = None,
    ) -> Any:
        op_name = context.operation or span_name or "operation"
        labels = {
            "environment": context.environment,
            "service": context.service_name,
            "operation": op_name,
        }
        span = None
        if self.policy.create_child_span:
            span = self.observability.tracing.start_span(
                name=span_name or op_name,
                service_name=context.service_name,
                environment=context.environment,
                parent=parent_span,
                kind=span_kind,
                attributes=attributes,
                baggage={
                    "correlation_id": context.correlation_id
                } if context.correlation_id else {},
            )
            context = replace(
                context,
                trace_id=span.trace_id,
                span_id=span.span_id,
            )

        if self.policy.emit_start_log:
            record = self.observability.logging.create_record(
                level="INFO",
                message=f"Operation started: {op_name}",
                context=context,
                event_name="operation.started",
                fields=attributes or {},
            )
            if record is not None:
                self.observability.logging.serialize(record)

        started = perf_counter()
        try:
            result = operation()
            duration = perf_counter() - started
            if self.policy.record_success_counter:
                self.observability.metrics.record(
                    name=f"{self.policy.metric_prefix}_operations_total",
                    value=1,
                    labels={**labels, "status": "success"},
                    exemplar_trace_id=span.trace_id if span else None,
                    exemplar_span_id=span.span_id if span else None,
                )
            if self.policy.record_duration_histogram:
                self.observability.metrics.record(
                    name=(
                        f"{self.policy.metric_prefix}_"
                        "operation_duration_seconds"
                    ),
                    value=duration,
                    labels=labels,
                    exemplar_trace_id=span.trace_id if span else None,
                    exemplar_span_id=span.span_id if span else None,
                )
            if self.policy.emit_completion_log:
                record = self.observability.logging.create_record(
                    level="INFO",
                    message=f"Operation completed: {op_name}",
                    context=context,
                    event_name="operation.completed",
                    fields={"duration_seconds": duration},
                )
                if record is not None:
                    self.observability.logging.serialize(record)
            if span:
                self.observability.tracing.end_span(span, status="OK")
            return result
        except BaseException as exc:
            duration = perf_counter() - started
            if self.policy.record_failure_counter:
                self.observability.metrics.record(
                    name=f"{self.policy.metric_prefix}_operations_total",
                    value=1,
                    labels={**labels, "status": "failure"},
                    exemplar_trace_id=span.trace_id if span else None,
                    exemplar_span_id=span.span_id if span else None,
                )
            if self.policy.record_duration_histogram:
                self.observability.metrics.record(
                    name=(
                        f"{self.policy.metric_prefix}_"
                        "operation_duration_seconds"
                    ),
                    value=duration,
                    labels=labels,
                    exemplar_trace_id=span.trace_id if span else None,
                    exemplar_span_id=span.span_id if span else None,
                )
            if self.policy.emit_failure_log:
                record = self.observability.logging.create_record(
                    level="ERROR",
                    message=f"Operation failed: {op_name}",
                    context=context,
                    event_name="operation.failed",
                    exception=exc,
                    fields={"duration_seconds": duration},
                )
                if record is not None:
                    self.observability.logging.serialize(record)
            if span:
                self.observability.tracing.end_span(span, error=exc)
            raise
