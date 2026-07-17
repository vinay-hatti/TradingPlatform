from __future__ import annotations

from pathlib import Path

from .distributed_tracing_service import DistributedTracingService
from .metrics_registry import MetricsRegistry
from .observability_policy import ObservabilityPolicy
from .structured_logging_service import StructuredLoggingService


class ObservabilityService:
    """Unified facade for structured logs, metrics, and traces."""

    def __init__(
        self,
        *,
        policy: ObservabilityPolicy | None = None,
        metrics_path: str | Path = (
            "data/observability/metrics_registry.json"
        ),
        traces_path: str | Path = (
            "data/observability/traces.json"
        ),
    ) -> None:
        self.policy = policy or ObservabilityPolicy()
        self.policy.validate()
        self.logging = StructuredLoggingService(self.policy.logging)
        self.metrics = MetricsRegistry(
            policy=self.policy.metrics,
            path=metrics_path,
        )
        self.tracing = DistributedTracingService(
            policy=self.policy.tracing,
            path=traces_path,
        )
