from __future__ import annotations

from pathlib import Path
import tempfile

from trading_ai.observability.export_buffer_repository import (
    JsonExportBufferRepository,
)
from trading_ai.observability.export_policy import (
    LogExportPolicy,
    MetricsAggregationPolicy,
    PrometheusExpositionPolicy,
    TraceExportPolicy,
)
from trading_ai.observability.log_export_pipeline import (
    LogExportPipeline,
)
from trading_ai.observability.metrics_aggregation_service import (
    MetricsAggregationService,
)
from trading_ai.observability.observability_profile import (
    MetricDefinition,
    MetricSample,
    ObservabilityContext,
    StructuredLogRecord,
    TraceRecord,
    TraceSpan,
)
from trading_ai.observability.prometheus_exposition_service import (
    PrometheusExpositionService,
)
from trading_ai.observability.trace_export_pipeline import (
    TraceExportPipeline,
)


def main() -> None:
    definitions = (
        MetricDefinition(
            name="trading_ai_orders_total",
            metric_type="COUNTER",
            description="Order count.",
            unit="orders",
            label_names=("environment", "status"),
        ),
        MetricDefinition(
            name="trading_ai_latency_seconds",
            metric_type="HISTOGRAM",
            description="Operation latency.",
            unit="seconds",
            label_names=("environment",),
        ),
        MetricDefinition(
            name="trading_ai_service_ready",
            metric_type="GAUGE",
            description="Service readiness.",
            label_names=("service",),
        ),
    )
    samples = (
        MetricSample(
            name="trading_ai_orders_total",
            metric_type="COUNTER",
            value=1,
            labels={"environment": "paper", "status": "accepted"},
        ),
        MetricSample(
            name="trading_ai_orders_total",
            metric_type="COUNTER",
            value=2,
            labels={"environment": "paper", "status": "accepted"},
        ),
        MetricSample(
            name="trading_ai_latency_seconds",
            metric_type="HISTOGRAM",
            value=0.1,
            labels={"environment": "paper"},
            exemplar_trace_id="a" * 32,
            exemplar_span_id="b" * 16,
        ),
        MetricSample(
            name="trading_ai_latency_seconds",
            metric_type="HISTOGRAM",
            value=0.7,
            labels={"environment": "paper"},
        ),
        MetricSample(
            name="trading_ai_service_ready",
            metric_type="GAUGE",
            value=1,
            labels={"service": "market-data"},
        ),
        MetricSample(
            name="trading_ai_service_ready",
            metric_type="GAUGE",
            value=0,
            labels={"service": "market-data"},
        ),
    )

    aggregation = MetricsAggregationService(
        MetricsAggregationPolicy(
            histogram_boundaries=(0.1, 0.5, 1.0)
        )
    )
    metrics = aggregation.aggregate(
        definitions=definitions,
        samples=samples,
    )
    counter = next(
        item for item in metrics
        if item.name == "trading_ai_orders_total"
    )
    assert counter.value == 3.0
    histogram = next(
        item for item in metrics
        if item.name == "trading_ai_latency_seconds"
    )
    assert histogram.sample_count == 2
    assert abs((histogram.sum_value or 0.0) - 0.8) < 1e-12
    assert histogram.buckets["0.1"] == 1
    assert histogram.buckets["0.5"] == 1
    assert histogram.buckets["1.0"] == 2
    gauge = next(
        item for item in metrics
        if item.name == "trading_ai_service_ready"
    )
    assert gauge.value == 0.0

    exposition = PrometheusExpositionService(
        PrometheusExpositionPolicy()
    ).render(
        definitions=definitions,
        metrics=metrics,
    )
    assert "# HELP trading_ai_orders_total Order count." in exposition
    assert "# TYPE trading_ai_orders_total counter" in exposition
    assert (
        'trading_ai_orders_total{environment="paper",status="accepted"} 3.0'
        in exposition
    )
    assert "# TYPE trading_ai_latency_seconds histogram" in exposition
    assert (
        'trading_ai_latency_seconds_bucket{environment="paper",le="1.0"} 2'
        in exposition
    )
    assert "trading_ai_latency_seconds_count{environment=\"paper\"} 2" in exposition

    with tempfile.TemporaryDirectory() as temp:
        repository = JsonExportBufferRepository(
            Path(temp) / "buffer.json"
        )
        logs = LogExportPipeline(
            policy=LogExportPolicy(
                batch_size=2,
                maximum_buffer_size=10,
                maximum_export_attempts=2,
                failure_mode="RETAIN",
            ),
            repository=repository,
        )
        traces = TraceExportPipeline(
            policy=TraceExportPolicy(
                batch_size=2,
                maximum_buffer_size=10,
                maximum_export_attempts=2,
                failure_mode="RETAIN",
            ),
            repository=repository,
        )

        context = ObservabilityContext(
            service_name="order-management",
            environment="paper",
        )
        logs.enqueue(StructuredLogRecord(
            level="INFO",
            message="one",
            context=context,
        ))
        logs.enqueue(StructuredLogRecord(
            level="ERROR",
            message="two",
            context=context,
        ))
        assert repository.count("LOG") == 2

        retained = logs.flush(lambda payloads: False)
        assert not retained.success
        assert retained.retained == 2
        assert repository.count("LOG") == 2

        exported_payloads = []
        exported = logs.flush(
            lambda payloads: exported_payloads.extend(payloads) or True
        )
        assert exported.success
        assert exported.exported == 2
        assert repository.count("LOG") == 0
        assert len(exported_payloads) == 2

        root = TraceSpan(
            trace_id="1" * 32,
            span_id="2" * 16,
            name="submit_order",
            service_name="order-management",
            environment="paper",
            end_time="2026-07-16T20:00:01+00:00",
            status="OK",
        )
        trace = TraceRecord(
            trace_id=root.trace_id,
            root_span_id=root.span_id,
            service_name=root.service_name,
            environment=root.environment,
            spans=(root,),
            started_at=root.start_time,
            completed_at=root.end_time,
            status="OK",
        )
        traces.enqueue(trace)
        assert repository.count("TRACE") == 1
        trace_result = traces.flush(lambda payloads: True)
        assert trace_result.exported == 1
        assert repository.count("TRACE") == 0
        assert (Path(temp) / "buffer.json").exists()

    print(
        "All metrics aggregation, Prometheus exposition, log export, "
        "and trace exporter foundation assertions passed."
    )


if __name__ == "__main__":
    main()
