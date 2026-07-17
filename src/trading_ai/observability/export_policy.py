from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MetricsAggregationPolicy:
    retention_seconds: float = 86400.0
    maximum_samples_per_series: int = 10000
    histogram_boundaries: tuple[float, ...] = (
        0.005, 0.01, 0.025, 0.05, 0.1, 0.25,
        0.5, 1.0, 2.5, 5.0, 10.0,
    )
    include_created_timestamp: bool = True

    def validate(self) -> None:
        if self.retention_seconds <= 0:
            raise ValueError("retention_seconds must be positive")
        if self.maximum_samples_per_series <= 0:
            raise ValueError(
                "maximum_samples_per_series must be positive"
            )
        if tuple(sorted(self.histogram_boundaries)) != (
            self.histogram_boundaries
        ):
            raise ValueError("histogram_boundaries must be sorted")


@dataclass(frozen=True)
class PrometheusExpositionPolicy:
    include_help: bool = True
    include_type: bool = True
    include_timestamps: bool = False
    openmetrics_eof: bool = False
    metric_name_prefix: str = ""

    def validate(self) -> None:
        if any(char.isspace() for char in self.metric_name_prefix):
            raise ValueError("metric_name_prefix cannot contain spaces")


@dataclass(frozen=True)
class LogExportPolicy:
    batch_size: int = 100
    maximum_buffer_size: int = 10000
    flush_interval_seconds: float = 5.0
    failure_mode: str = "RETAIN"
    persist_buffer: bool = True
    maximum_export_attempts: int = 3

    def validate(self) -> None:
        if self.batch_size <= 0:
            raise ValueError("batch_size must be positive")
        if self.maximum_buffer_size < self.batch_size:
            raise ValueError(
                "maximum_buffer_size must be >= batch_size"
            )
        if self.flush_interval_seconds <= 0:
            raise ValueError(
                "flush_interval_seconds must be positive"
            )
        if self.failure_mode not in {"RETAIN", "DROP"}:
            raise ValueError("failure_mode must be RETAIN or DROP")
        if self.maximum_export_attempts <= 0:
            raise ValueError(
                "maximum_export_attempts must be positive"
            )


@dataclass(frozen=True)
class TraceExportPolicy:
    batch_size: int = 50
    maximum_buffer_size: int = 5000
    flush_interval_seconds: float = 5.0
    failure_mode: str = "RETAIN"
    persist_buffer: bool = True
    maximum_export_attempts: int = 3

    def validate(self) -> None:
        if self.batch_size <= 0:
            raise ValueError("batch_size must be positive")
        if self.maximum_buffer_size < self.batch_size:
            raise ValueError(
                "maximum_buffer_size must be >= batch_size"
            )
        if self.flush_interval_seconds <= 0:
            raise ValueError(
                "flush_interval_seconds must be positive"
            )
        if self.failure_mode not in {"RETAIN", "DROP"}:
            raise ValueError("failure_mode must be RETAIN or DROP")
        if self.maximum_export_attempts <= 0:
            raise ValueError(
                "maximum_export_attempts must be positive"
            )


@dataclass(frozen=True)
class ObservabilityExportPolicy:
    aggregation: MetricsAggregationPolicy = MetricsAggregationPolicy()
    prometheus: PrometheusExpositionPolicy = (
        PrometheusExpositionPolicy()
    )
    logs: LogExportPolicy = LogExportPolicy()
    traces: TraceExportPolicy = TraceExportPolicy()

    def validate(self) -> None:
        self.aggregation.validate()
        self.prometheus.validate()
        self.logs.validate()
        self.traces.validate()
