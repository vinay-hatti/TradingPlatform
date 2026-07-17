from __future__ import annotations

from pathlib import Path

from .instrumentation_policy import ObservabilityInstrumentationPolicy
from .observability_service import ObservabilityService
from .operation_instrumentation_service import (
    OperationInstrumentationService,
)
from .operational_resilience_observer import (
    OperationalResilienceObserver,
)
from .runtime_metrics_collector import RuntimeMetricsCollector
from .trace_propagation import TracePropagationService


class InstrumentedObservabilityService:
    """Unified Phase 9 Step 2 facade."""

    def __init__(
        self,
        *,
        observability: ObservabilityService | None = None,
        policy: ObservabilityInstrumentationPolicy | None = None,
        metrics_path: str | Path = (
            "data/observability/metrics_registry.json"
        ),
        traces_path: str | Path = (
            "data/observability/traces.json"
        ),
    ) -> None:
        self.policy = policy or ObservabilityInstrumentationPolicy()
        self.policy.validate()
        self.observability = observability or ObservabilityService(
            metrics_path=metrics_path,
            traces_path=traces_path,
        )
        self.operations = OperationInstrumentationService(
            observability=self.observability,
            policy=self.policy.operation,
        )
        self.runtime_metrics = RuntimeMetricsCollector(
            registry=self.observability.metrics,
            policy=self.policy.runtime,
            metric_prefix=self.policy.operation.metric_prefix,
        )
        self.propagation = TracePropagationService(
            self.policy.propagation
        )
        self.operational_resilience = OperationalResilienceObserver(
            observability=self.observability,
            metrics=self.runtime_metrics,
        )
