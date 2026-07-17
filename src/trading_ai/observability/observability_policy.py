from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class StructuredLoggingPolicy:
    minimum_level: str = "INFO"
    include_timestamp: bool = True
    include_service_context: bool = True
    include_trace_context: bool = True
    redact_sensitive_fields: bool = True
    sensitive_field_names: tuple[str, ...] = (
        "password",
        "secret",
        "token",
        "api_key",
        "authorization",
        "cookie",
    )
    maximum_message_length: int = 8192
    fail_closed_on_serialization_error: bool = True

    def validate(self) -> None:
        levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        if self.minimum_level.upper() not in levels:
            raise ValueError("minimum_level is invalid")
        if self.maximum_message_length <= 0:
            raise ValueError("maximum_message_length must be positive")


@dataclass(frozen=True)
class MetricsPolicy:
    maximum_unique_series: int = 10000
    maximum_label_count: int = 12
    maximum_label_value_length: int = 128
    allow_dynamic_metric_registration: bool = True
    reject_invalid_values: bool = True
    persist_registry: bool = True

    def validate(self) -> None:
        if self.maximum_unique_series <= 0:
            raise ValueError("maximum_unique_series must be positive")
        if self.maximum_label_count < 0:
            raise ValueError("maximum_label_count cannot be negative")
        if self.maximum_label_value_length <= 0:
            raise ValueError(
                "maximum_label_value_length must be positive"
            )


@dataclass(frozen=True)
class DistributedTracingPolicy:
    sampling_rate: float = 1.0
    maximum_span_attributes: int = 32
    maximum_span_events: int = 64
    maximum_attribute_value_length: int = 512
    propagate_baggage: bool = True
    persist_completed_traces: bool = True
    fail_closed_on_invalid_parent: bool = True

    def validate(self) -> None:
        if not 0 <= self.sampling_rate <= 1:
            raise ValueError("sampling_rate must be between 0 and 1")
        if self.maximum_span_attributes <= 0:
            raise ValueError("maximum_span_attributes must be positive")
        if self.maximum_span_events <= 0:
            raise ValueError("maximum_span_events must be positive")
        if self.maximum_attribute_value_length <= 0:
            raise ValueError(
                "maximum_attribute_value_length must be positive"
            )


@dataclass(frozen=True)
class ObservabilityPolicy:
    logging: StructuredLoggingPolicy = StructuredLoggingPolicy()
    metrics: MetricsPolicy = MetricsPolicy()
    tracing: DistributedTracingPolicy = DistributedTracingPolicy()

    def validate(self) -> None:
        self.logging.validate()
        self.metrics.validate()
        self.tracing.validate()
