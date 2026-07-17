from __future__ import annotations

from datetime import datetime, timedelta, timezone
import tempfile
from pathlib import Path

from trading_ai.operational_resilience.runtime_health_registry import (
    JsonRuntimeHealthRegistry,
)
from trading_ai.operational_resilience.service_health_profile import (
    DependencyHealth,
    ServiceHeartbeat,
)
from trading_ai.operational_resilience.service_health_serialization import (
    dumps,
)
from trading_ai.operational_resilience.service_health_service import (
    ServiceHealthService,
)


def main() -> None:
    now = datetime.now(timezone.utc)

    heartbeats = (
        ServiceHeartbeat(
            service_name="market-data",
            instance_id="market-data-1",
            environment="paper",
            status="RUNNING",
            timestamp=now.isoformat(),
            sequence=101,
            version="1.0.0",
            host="localhost",
            process_id=10101,
            critical=True,
        ),
        ServiceHeartbeat(
            service_name="order-management",
            instance_id="order-management-1",
            environment="paper",
            status="READY",
            timestamp=now.isoformat(),
            sequence=202,
            version="1.0.0",
            host="localhost",
            process_id=20202,
            critical=True,
        ),
    )

    dependencies = {
        "market-data": (
            DependencyHealth(
                dependency_name="postgresql",
                dependency_type="DATABASE",
                status="UP",
                checked_at=now.isoformat(),
                critical=True,
                latency_ms=4.2,
            ),
            DependencyHealth(
                dependency_name="market-provider",
                dependency_type="EXTERNAL_API",
                status="UP",
                checked_at=now.isoformat(),
                critical=True,
                latency_ms=15.0,
            ),
        ),
        "order-management": (
            DependencyHealth(
                dependency_name="postgresql",
                dependency_type="DATABASE",
                status="UP",
                checked_at=now.isoformat(),
                critical=True,
                latency_ms=4.0,
            ),
            DependencyHealth(
                dependency_name="paper-broker",
                dependency_type="BROKER",
                status="UP",
                checked_at=now.isoformat(),
                critical=True,
                latency_ms=8.0,
            ),
        ),
    }

    with tempfile.TemporaryDirectory() as temp:
        registry = JsonRuntimeHealthRegistry(
            Path(temp) / "runtime_health.json"
        )
        service = ServiceHealthService(registry=registry)

        healthy = service.evaluate_and_publish(
            registry_id="paper-runtime",
            environment="paper",
            heartbeats=heartbeats,
            dependencies_by_service=dependencies,
            as_of=now,
        )
        assert healthy.allowed
        assert healthy.recommendation == "READY"
        assert healthy.state is not None
        assert healthy.state.overall_status == "HEALTHY"
        assert healthy.state.service_count == 2
        assert healthy.state.ready_service_count == 2
        assert healthy.state.healthy_service_count == 2
        assert healthy.state.version == 1

        persisted = registry.get("paper-runtime")
        assert persisted is not None
        assert persisted.version == 1
        assert persisted.services[0].dependencies

        degraded_dependencies = dict(dependencies)
        degraded_dependencies["market-data"] = (
            DependencyHealth(
                dependency_name="postgresql",
                dependency_type="DATABASE",
                status="UP",
                checked_at=now.isoformat(),
                critical=True,
            ),
            DependencyHealth(
                dependency_name="market-provider",
                dependency_type="EXTERNAL_API",
                status="DEGRADED",
                checked_at=now.isoformat(),
                critical=True,
                message="Rate limited",
            ),
        )
        degraded = service.evaluate_and_publish(
            registry_id="paper-runtime",
            environment="paper",
            heartbeats=heartbeats,
            dependencies_by_service=degraded_dependencies,
            as_of=now,
        )
        assert degraded.allowed
        assert degraded.recommendation == "DEGRADED_READY"
        assert degraded.state is not None
        assert degraded.state.version == 2
        assert degraded.state.degraded_service_count == 1

        stale_heartbeats = (
            ServiceHeartbeat(
                **{
                    **heartbeats[0].__dict__,
                    "timestamp": (
                        now - timedelta(seconds=180)
                    ).isoformat(),
                }
            ),
            heartbeats[1],
        )
        failed = service.evaluate_and_publish(
            registry_id="paper-runtime",
            environment="paper",
            heartbeats=stale_heartbeats,
            dependencies_by_service=dependencies,
            as_of=now,
        )
        assert not failed.allowed
        assert failed.recommendation == "NOT_READY"
        assert failed.state is not None
        assert failed.state.version == 3
        assert failed.state.critical_failure_count == 1
        assert "CRITICAL_SERVICES_READY" in failed.rejection_reasons
        assert "DEAD_HEARTBEAT:market-data" in failed.warnings

        failed_dependency = {
            **dependencies,
            "order-management": (
                DependencyHealth(
                    dependency_name="postgresql",
                    dependency_type="DATABASE",
                    status="FAILED",
                    checked_at=now.isoformat(),
                    critical=True,
                    consecutive_failures=3,
                ),
            ),
        }
        dependency_failure = service.evaluate_and_publish(
            registry_id="paper-runtime",
            environment="paper",
            heartbeats=heartbeats,
            dependencies_by_service=failed_dependency,
            as_of=now,
        )
        assert not dependency_failure.allowed
        assert dependency_failure.state is not None
        assert dependency_failure.state.version == 4
        assert (
            "DEPENDENCY_FAILED:postgresql"
            in dependency_failure.warnings
        )

        latest = registry.latest_for_environment("paper")
        assert latest is not None
        assert latest.version == 4

        payload = dumps(healthy)
        assert '"registry_id": "paper-runtime"' in payload
        assert '"overall_status": "HEALTHY"' in payload
        assert '"recommendation": "READY"' in payload

    print(
        "All service-health contracts, heartbeat, dependency-readiness, "
        "and runtime-registry assertions passed."
    )


if __name__ == "__main__":
    main()
