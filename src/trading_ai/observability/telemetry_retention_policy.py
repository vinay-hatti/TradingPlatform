from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TelemetryRetentionRule:
    telemetry_type: str
    retention_seconds: float
    archive_before_delete: bool = False
    maximum_records: int | None = None

    def validate(self) -> None:
        if self.retention_seconds <= 0:
            raise ValueError("retention_seconds must be positive")
        if self.maximum_records is not None and self.maximum_records <= 0:
            raise ValueError("maximum_records must be positive")


@dataclass(frozen=True)
class TelemetryRetentionPolicy:
    metrics: TelemetryRetentionRule = TelemetryRetentionRule(
        telemetry_type="METRIC",
        retention_seconds=86400.0 * 30,
        maximum_records=100000,
    )
    logs: TelemetryRetentionRule = TelemetryRetentionRule(
        telemetry_type="LOG",
        retention_seconds=86400.0 * 14,
        archive_before_delete=True,
        maximum_records=100000,
    )
    traces: TelemetryRetentionRule = TelemetryRetentionRule(
        telemetry_type="TRACE",
        retention_seconds=86400.0 * 7,
        archive_before_delete=True,
        maximum_records=50000,
    )
    exports: TelemetryRetentionRule = TelemetryRetentionRule(
        telemetry_type="EXPORT",
        retention_seconds=86400.0 * 3,
        maximum_records=50000,
    )

    def validate(self) -> None:
        self.metrics.validate()
        self.logs.validate()
        self.traces.validate()
        self.exports.validate()
