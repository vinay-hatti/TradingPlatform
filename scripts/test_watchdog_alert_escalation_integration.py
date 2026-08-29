from __future__ import annotations
from datetime import datetime, timezone
import tempfile
from pathlib import Path

from trading_ai.operational_resilience.operational_watchdog_service import (
    OperationalWatchdogService,
)
from trading_ai.operational_resilience.recovery_policy import (
    IncidentPolicy,
    RecoveryGovernancePolicy,
    RecoveryWorkflowPolicy,
    ServiceRestartPolicy,
)
from trading_ai.operational_resilience.recovery_repository import (
    JsonRecoveryRepository,
)
from trading_ai.operational_resilience.recovery_workflow_engine import (
    RecoveryWorkflowEngine,
)
from trading_ai.operational_resilience.service_health_engine import (
    ServiceHealthEngine,
)
from trading_ai.operational_resilience.service_health_profile import (
    DependencyHealth,
    ServiceHeartbeat,
)
from trading_ai.operational_resilience.watchdog_policy import (
    HealthAlertRoutingPolicy,
    IncidentEscalationPolicy,
    OperationalWatchdogPolicy,
    WatchdogGovernancePolicy,
)
from trading_ai.operational_resilience.watchdog_repository import (
    JsonWatchdogRepository,
)
from trading_ai.operational_resilience.watchdog_serialization import dumps

def main() -> None:
    now = datetime.now(timezone.utc)
    health_engine = ServiceHealthEngine()

    healthy = health_engine.evaluate(
        registry_id="paper-runtime",
        environment="paper",
        heartbeats=(
            ServiceHeartbeat(
                service_name="market-data",
                instance_id="md-1",
                environment="paper",
                status="RUNNING",
                timestamp=now.isoformat(),
                critical=True,
            ),
        ),
        dependencies_by_service={
            "market-data": (
                DependencyHealth(
                    dependency_name="postgresql",
                    dependency_type="DATABASE",
                    status="UP",
                    checked_at=now.isoformat(),
                    critical=True,
                ),
            )
        },
        as_of=now,
    )
    assert healthy.allowed

    failed = health_engine.evaluate(
        registry_id="paper-runtime",
        environment="paper",
        heartbeats=(
            ServiceHeartbeat(
                service_name="broker-adapter",
                instance_id="broker-1",
                environment="paper",
                status="FAILED",
                timestamp=now.isoformat(),
                critical=True,
            ),
        ),
        dependencies_by_service={
            "broker-adapter": (
                DependencyHealth(
                    dependency_name="broker",
                    dependency_type="BROKER",
                    status="FAILED",
                    checked_at=now.isoformat(),
                    critical=True,
                    consecutive_failures=3,
                ),
            )
        },
        as_of=now,
    )
    assert not failed.allowed

    with tempfile.TemporaryDirectory() as temp:
        watchdog_repo = JsonWatchdogRepository(
            Path(temp) / "watchdog.json"
        )
        recovery_repo = JsonRecoveryRepository(
            Path(temp) / "recovery.json"
        )
        recovery_engine = RecoveryWorkflowEngine(
            policy=RecoveryGovernancePolicy(
                workflow=RecoveryWorkflowPolicy(
                    maximum_recovery_attempts=1
                ),
                restart=ServiceRestartPolicy(
                    maximum_restarts_per_window=10,
                    minimum_restart_interval_seconds=0.0,
                ),
                incident=IncidentPolicy(),
            ),
            repository=recovery_repo,
        )
        service = OperationalWatchdogService(
            policy=WatchdogGovernancePolicy(
                alerts=HealthAlertRoutingPolicy(
                    deduplication_window_seconds=300.0
                ),
                escalation=IncidentEscalationPolicy(
                    severe_escalation_seconds=60.0,
                    critical_escalation_seconds=30.0,
                    maximum_escalation_level=3,
                ),
                watchdog=OperationalWatchdogPolicy(),
            ),
            watchdog_repository=watchdog_repo,
            recovery_repository=recovery_repo,
            recovery_engine=recovery_engine,
        )

        healthy_cycle = service.run_cycle(
            environment="paper",
            health_decision=healthy,
            restart_callable_factory=lambda _: (lambda: True),
            health_verifier_factory=lambda _: (lambda: True),
            as_of=now,
        )
        assert healthy_cycle.allowed
        assert healthy_cycle.recommendation == "MONITOR"
        assert healthy_cycle.cycle_state.sequence_number == 1
        assert healthy_cycle.cycle_state.alert_count == 0

        failed_cycle = service.run_cycle(
            environment="paper",
            health_decision=failed,
            restart_callable_factory=lambda _: (lambda: False),
            health_verifier_factory=lambda _: (lambda: False),
            as_of=now,
        )
        assert not failed_cycle.allowed
        assert failed_cycle.recommendation == "RECOVERY_REQUIRED"
        assert len(failed_cycle.alerts) == 1
        assert failed_cycle.alerts[0].severity == "CRITICAL"
        assert "PAGER" in failed_cycle.alerts[0].channels
        assert len(failed_cycle.recovery_workflow_ids) == 1
        assert len(failed_cycle.incident_ids) == 1
        assert len(failed_cycle.escalations) == 1
        assert failed_cycle.escalations[0].level == 1
        assert failed_cycle.escalations[0].target_role == (
            "ON_CALL_OPERATIONS"
        )
        assert failed_cycle.cycle_state.sequence_number == 2

        repeated = service.run_cycle(
            environment="paper",
            health_decision=failed,
            restart_callable_factory=lambda _: (lambda: False),
            health_verifier_factory=lambda _: (lambda: False),
            as_of=now,
        )
        assert repeated.alerts[0].occurrence_count == 2
        assert repeated.cycle_state.sequence_number == 3

        latest = watchdog_repo.latest_cycle("paper")
        assert latest is not None
        assert latest.sequence_number == 3
        assert latest.status == "COMPLETED"

        payload = dumps(failed_cycle)
        assert '"recommendation": "RECOVERY_REQUIRED"' in payload
        assert '"severity": "CRITICAL"' in payload
        assert '"target_role": "ON_CALL_OPERATIONS"' in payload

    print(
        "All health-alert routing, incident-escalation, operational-watchdog, "
        "and recovery-orchestration integration assertions passed."
    )

if __name__ == "__main__":
    main()
