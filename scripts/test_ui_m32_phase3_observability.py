from pathlib import Path
from tempfile import TemporaryDirectory

from fastapi.testclient import TestClient

from trading_ai.ui.api.observability import service as service_dependency
from trading_ai.ui.app import create_app
from trading_ai.ui.observability.metrics_registry import MetricsRegistry
from trading_ai.ui.observability.structured_logging import StructuredLogManager
from trading_ai.ui.services.observability_service import ObservabilityService


def main():
    with TemporaryDirectory() as directory:
        root = Path(directory)
        metrics = MetricsRegistry()
        metrics.increment("phase3_test_counter")
        metrics.gauge("phase3_test_gauge", 12.5)

        log_path = root / "workstation.jsonl"
        logger = StructuredLogManager(log_path)
        logger.emit(
            message="Phase 3 structured logging test",
            event_type="TEST",
            component="regression",
            outcome="SUCCESS",
        )
        assert log_path.exists()
        assert '"event_type": "TEST"' in log_path.read_text(encoding="utf-8")

        service = ObservabilityService(
            metrics=metrics,
            log_path=log_path,
            alert_path=root / "alerts.json",
            command_state_path=root / "commands.json",
            broker_state_path=root / "broker.json",
            minimum_free_disk_mb=1.0,
        )

        state = service.state()
        assert state.summary.liveness_status == "HEALTHY"
        assert state.summary.readiness_status == "HEALTHY"
        assert state.summary.metric_count >= 2
        assert any(
            check.name == "structured_logging"
            and check.status == "HEALTHY"
            for check in state.health_checks
        )
        assert state.summary.warning_alert_count >= 2

        active_alert = next(
            alert for alert in state.alerts if alert.status == "ACTIVE"
        )
        acknowledged = service.acknowledge(
            active_alert.alert_id,
            "phase3-tester",
            "Regression acknowledgement",
        )
        assert acknowledged.acknowledged is True

        app = create_app()
        app.dependency_overrides[service_dependency] = lambda: service
        client = TestClient(app)

        live = client.get("/api/v1/observability/health/live")
        assert live.status_code == 200
        assert live.json()["status"] == "HEALTHY"

        ready = client.get("/api/v1/observability/health/ready")
        assert ready.status_code == 200

        snapshot = client.get("/api/v1/observability")
        assert snapshot.status_code == 200
        assert "health_checks" in snapshot.json()

        metrics_response = client.get("/api/v1/observability/metrics")
        assert metrics_response.status_code == 200
        assert "http_requests_total" in metrics_response.text

        assert client.get("/api/v1/observability").headers.get(
            "x-correlation-id"
        )

    print(
        "All Milestone 32 Phase 3 Operational Metrics, Structured Logging, "
        "Health Probes, Alerting, and Observability assertions passed."
    )


if __name__ == "__main__":
    main()
