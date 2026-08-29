from __future__ import annotations

import json
from pathlib import Path
import tempfile

from trading_ai.observability import (
    MetricDefinition,
    ObservabilityContext,
    ObservabilityService,
)


def main() -> None:
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        service = ObservabilityService(
            metrics_path=root / "metrics.json",
            traces_path=root / "traces.json",
        )

        context = ObservabilityContext(
            service_name="order-management",
            environment="paper",
            instance_id="oms-1",
            component="submission",
            operation="submit_order",
            trace_id="trace-1",
            span_id="span-1",
            correlation_id="corr-1",
            metadata={"token": "hidden", "desk": "systematic"},
        )
        record = service.logging.create_record(
            level="INFO",
            message="Order submission accepted",
            context=context,
            event_name="order.accepted",
            fields={
                "order_id": "O-1",
                "authorization": "Bearer secret",
                "nested": {"password": "secret"},
            },
        )
        assert record is not None
        serialized = service.logging.serialize(record)
        payload = json.loads(serialized)
        assert payload["fields"]["authorization"] == "[REDACTED]"
        assert payload["fields"]["nested"]["password"] == "[REDACTED]"
        assert payload["context"]["metadata"]["token"] == "[REDACTED]"
        assert payload["context"]["trace_id"] == "trace-1"

        service.metrics.register(
            MetricDefinition(
                name="trading_ai_order_submissions_total",
                metric_type="COUNTER",
                description="Submitted order count.",
                unit="orders",
                label_names=("environment", "status"),
            )
        )
        sample = service.metrics.record(
            name="trading_ai_order_submissions_total",
            value=1,
            labels={
                "environment": "paper",
                "status": "accepted",
            },
            exemplar_trace_id="trace-1",
            exemplar_span_id="span-1",
        )
        assert sample.value == 1.0
        assert sample.exemplar_trace_id == "trace-1"
        assert len(service.metrics.definitions()) == 1
        assert len(
            service.metrics.samples(
                "trading_ai_order_submissions_total"
            )
        ) == 1
        assert (root / "metrics.json").exists()

        root_span = service.tracing.start_span(
            name="submit_order",
            service_name="order-management",
            environment="paper",
            kind="SERVER",
            attributes={"order.id": "O-1"},
            baggage={"correlation_id": "corr-1"},
        )
        child = service.tracing.start_span(
            name="broker_submit",
            service_name="broker-adapter",
            environment="paper",
            parent=root_span,
            kind="CLIENT",
            attributes={"broker": "paper"},
        )
        child = service.tracing.add_event(
            child,
            name="request.sent",
            attributes={"attempt": 1},
        )
        completed_child = service.tracing.end_span(
            child,
            status="OK",
        )
        assert completed_child.parent_span_id == root_span.span_id
        assert completed_child.baggage["correlation_id"] == "corr-1"

        completed_root = service.tracing.end_span(
            root_span,
            status="OK",
        )
        assert completed_root.status == "OK"
        traces = service.tracing.traces()
        assert len(traces) == 1
        assert traces[0].trace_id == root_span.trace_id
        assert len(traces[0].spans) == 2
        assert traces[0].status == "OK"
        assert (root / "traces.json").exists()

        error_root = service.tracing.start_span(
            name="market_data_poll",
            service_name="market-data",
            environment="paper",
        )
        completed_error = service.tracing.end_span(
            error_root,
            error=TimeoutError("provider timeout"),
        )
        assert completed_error.status == "ERROR"
        assert completed_error.error_type == "TimeoutError"
        assert len(service.tracing.traces()) == 2
        assert service.tracing.traces()[1].status == "ERROR"

    print(
        "All structured-logging, metrics-registry, and "
        "distributed-tracing foundation assertions passed."
    )


if __name__ == "__main__":
    main()
