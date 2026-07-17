from __future__ import annotations
from dataclasses import replace
from datetime import datetime, timedelta, timezone
import tempfile
from pathlib import Path

from trading_ai.operational_resilience.incident_engine import IncidentEngine
from trading_ai.operational_resilience.recovery_policy import (
    IncidentPolicy,
    RecoveryGovernancePolicy,
    RecoveryWorkflowPolicy,
    ServiceRestartPolicy,
)
from trading_ai.operational_resilience.recovery_repository import (
    JsonRecoveryRepository,
)
from trading_ai.operational_resilience.recovery_serialization import dumps
from trading_ai.operational_resilience.recovery_workflow_engine import (
    RecoveryWorkflowEngine,
)
from trading_ai.operational_resilience.service_restart_engine import (
    ServiceRestartEngine,
)

def main() -> None:
    now = datetime.now(timezone.utc)
    restart_engine = ServiceRestartEngine(ServiceRestartPolicy(
        maximum_restarts_per_window=2,
        restart_window_seconds=300.0,
        minimum_restart_interval_seconds=10.0,
    ))
    authorized = restart_engine.authorize(
        service_name="market-data",
        instance_id="md-1",
        environment="paper",
        reason="dead-heartbeat",
        requested_by="test",
        critical=True,
        prior_restarts=(),
        as_of=now,
    )
    assert authorized.approved
    completed = restart_engine.execute(
        authorized,
        restart_callable=lambda: True,
        as_of=now,
    )
    assert completed.status == "COMPLETED"

    cooldown = restart_engine.authorize(
        service_name="market-data",
        instance_id="md-1",
        environment="paper",
        reason="dead-heartbeat",
        requested_by="test",
        critical=True,
        prior_restarts=(authorized,),
        as_of=now + timedelta(seconds=5),
    )
    assert not cooldown.approved
    assert cooldown.failure_message == "RESTART_COOLDOWN_ACTIVE"

    incident_engine = IncidentEngine(IncidentPolicy())
    incident = incident_engine.open_incident(
        service_name="broker",
        environment="paper",
        title="Broker unavailable",
        critical=True,
        workflow_id="wf-1",
    )
    assert incident.status == "OPEN"
    assert incident.severity == "CRITICAL"
    acknowledged = incident_engine.acknowledge(
        incident, actor="operator"
    )
    assert acknowledged.status == "ACKNOWLEDGED"
    resolved = incident_engine.resolve(
        acknowledged, note="Provider restored"
    )
    assert resolved.status == "RESOLVED"

    with tempfile.TemporaryDirectory() as temp:
        repository = JsonRecoveryRepository(
            Path(temp) / "recovery.json"
        )
        policy = RecoveryGovernancePolicy(
            workflow=RecoveryWorkflowPolicy(
                maximum_recovery_attempts=2
            ),
            restart=ServiceRestartPolicy(
                maximum_restarts_per_window=5,
                minimum_restart_interval_seconds=0.0,
            ),
            incident=IncidentPolicy(),
        )
        engine = RecoveryWorkflowEngine(
            policy=policy,
            repository=repository,
        )

        restart_calls = {"count": 0}
        verify_calls = {"count": 0}
        def restart_ok():
            restart_calls["count"] += 1
            return True
        def verify_on_second():
            verify_calls["count"] += 1
            return verify_calls["count"] >= 2

        recovered = engine.execute(
            service_name="order-management",
            instance_id="oms-1",
            environment="paper",
            trigger="critical-dependency-failure",
            critical=True,
            restart_callable=restart_ok,
            health_verifier=verify_on_second,
        )
        assert recovered.allowed
        assert recovered.recommendation == "RECOVERED"
        assert recovered.state is not None
        assert recovered.state.status == "COMPLETED"
        assert recovered.state.attempt_count == 2
        assert len(recovered.audit_entries) >= 5
        persisted = repository.get_workflow(
            recovered.workflow_id
        )
        assert persisted is not None
        assert persisted.status == "COMPLETED"
        assert len(
            repository.audits_for_entity(recovered.workflow_id)
        ) == len(recovered.audit_entries)

        exhausted = engine.execute(
            service_name="broker-adapter",
            instance_id="broker-1",
            environment="paper",
            trigger="open-circuit",
            critical=True,
            restart_callable=lambda: False,
            health_verifier=lambda: False,
        )
        assert not exhausted.allowed
        assert exhausted.recommendation == "INCIDENT_OPENED"
        assert exhausted.incident is not None
        assert exhausted.incident.status == "OPEN"
        assert exhausted.incident.severity == "CRITICAL"
        assert exhausted.state is not None
        assert exhausted.state.failure_reason == (
            "RECOVERY_ATTEMPTS_EXHAUSTED"
        )
        saved_incident = repository.get_incident(
            exhausted.incident.incident_id
        )
        assert saved_incident is not None

        blocked_engine = RecoveryWorkflowEngine(
            policy=RecoveryGovernancePolicy(
                workflow=RecoveryWorkflowPolicy(),
                restart=ServiceRestartPolicy(
                    require_manual_approval_for_critical_services=True
                ),
                incident=IncidentPolicy(),
            ),
            repository=repository,
        )
        blocked = blocked_engine.execute(
            service_name="risk-gateway",
            instance_id="risk-1",
            environment="paper",
            trigger="health-check-failed",
            critical=True,
            restart_callable=lambda: True,
            health_verifier=lambda: True,
        )
        assert not blocked.allowed
        assert blocked.recommendation == "MANUAL_INTERVENTION"
        assert blocked.incident is not None
        assert "MANUAL_APPROVAL_REQUIRED" in (
            blocked.rejection_reasons
        )

        payload = dumps(recovered)
        assert '"recommendation": "RECOVERED"' in payload
        assert '"service_name": "order-management"' in payload

    print(
        "All automatic-recovery, restart-governance, incident-contract, "
        "and recovery-audit assertions passed."
    )

if __name__ == "__main__":
    main()
