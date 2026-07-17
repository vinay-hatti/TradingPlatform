from __future__ import annotations

from pathlib import Path

from .export_buffer_repository import JsonExportBufferRepository
from .export_policy import ObservabilityExportPolicy
from .log_export_pipeline import LogExportPipeline
from .metrics_aggregation_service import MetricsAggregationService
from .prometheus_exposition_service import (
    PrometheusExpositionService,
)
from .trace_export_pipeline import TraceExportPipeline


class ObservabilityExportService:
    """Unified metrics, logs, and traces export foundation."""

    def __init__(
        self,
        *,
        policy: ObservabilityExportPolicy | None = None,
        buffer_path: str | Path = (
            "data/observability/export_buffer.json"
        ),
    ) -> None:
        self.policy = policy or ObservabilityExportPolicy()
        self.policy.validate()
        self.repository = JsonExportBufferRepository(buffer_path)
        self.aggregation = MetricsAggregationService(
            self.policy.aggregation
        )
        self.prometheus = PrometheusExpositionService(
            self.policy.prometheus
        )
        self.logs = LogExportPipeline(
            policy=self.policy.logs,
            repository=self.repository,
        )
        self.traces = TraceExportPipeline(
            policy=self.policy.traces,
            repository=self.repository,
        )
