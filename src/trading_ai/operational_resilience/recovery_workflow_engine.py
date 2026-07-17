from __future__ import annotations
from dataclasses import replace
from datetime import datetime, timezone
import hashlib
from typing import Callable

from .incident_engine import IncidentEngine
from .recovery_policy import RecoveryGovernancePolicy
from .recovery_profile import (
    RecoveryAction,
    RecoveryAuditEntry,
    RecoveryDecision,
    RecoveryWorkflowState,
)
from .recovery_repository import JsonRecoveryRepository
from .service_restart_engine import ServiceRestartEngine

class RecoveryWorkflowEngine:
    def __init__(
        self,
        *,
        policy: RecoveryGovernancePolicy | None = None,
        repository: JsonRecoveryRepository | None = None,
    ) -> None:
        self.policy = policy or RecoveryGovernancePolicy()
        self.policy.validate()
        self.repository = repository or JsonRecoveryRepository()
        self.restart_engine = ServiceRestartEngine(self.policy.restart)
        self.incident_engine = IncidentEngine(self.policy.incident)

    @staticmethod
    def _id(prefix: str, raw: str) -> str:
        return prefix + "-" + hashlib.sha256(raw.encode()).hexdigest()[:16]

    def execute(
        self,
        *,
        service_name: str,
        instance_id: str,
        environment: str,
        trigger: str,
        critical: bool,
        restart_callable: Callable[[], bool],
        health_verifier: Callable[[], bool],
        requested_by: str = "recovery-engine",
    ) -> RecoveryDecision:
        now = datetime.now(timezone.utc)
        workflow_id = self._id(
            "recovery",
            f"{service_name}:{instance_id}:{now.isoformat()}",
        )
        audits = []
        actions = []
        state = RecoveryWorkflowState(
            workflow_id=workflow_id,
            service_name=service_name,
            instance_id=instance_id,
            environment=environment,
            trigger=trigger,
            status="RUNNING",
            current_step="AUTHORIZE_RESTART",
            attempt_count=0,
            started_at=now.isoformat(),
            updated_at=now.isoformat(),
        )
        self.repository.save_workflow(state)

        def audit(action: str, outcome: str, details: dict | None = None):
            entry = RecoveryAuditEntry(
                audit_id=self._id(
                    "audit",
                    f"{workflow_id}:{action}:{len(audits)}",
                ),
                entity_type="RECOVERY_WORKFLOW",
                entity_id=workflow_id,
                action=action,
                actor=requested_by,
                outcome=outcome,
                details=details or {},
            )
            self.repository.append_audit(entry)
            audits.append(entry)

        audit("WORKFLOW_STARTED", "SUCCESS", {"trigger": trigger})

        prior = self.repository.restarts_for_service(service_name)
        restart = self.restart_engine.authorize(
            service_name=service_name,
            instance_id=instance_id,
            environment=environment,
            reason=trigger,
            requested_by=requested_by,
            critical=critical,
            prior_restarts=prior,
            as_of=now,
        )
        self.repository.save_restart(restart)
        audit(
            "RESTART_AUTHORIZATION",
            "APPROVED" if restart.approved else "REJECTED",
            {"restart_id": restart.restart_id},
        )

        if not restart.approved:
            incident = self.incident_engine.open_incident(
                service_name=service_name,
                environment=environment,
                title=f"Automatic recovery blocked for {service_name}",
                critical=critical,
                workflow_id=workflow_id,
                metadata={"reason": restart.failure_message},
            )
            self.repository.save_incident(incident)
            state = replace(
                state,
                status="FAILED",
                current_step="INCIDENT_OPENED",
                restart_record=restart,
                incident=incident,
                failure_reason=restart.failure_message,
                completed_at=datetime.now(timezone.utc).isoformat(),
                updated_at=datetime.now(timezone.utc).isoformat(),
                version=state.version + 1,
            )
            self.repository.save_workflow(state)
            audit("INCIDENT_OPENED", "SUCCESS", {
                "incident_id": incident.incident_id
            })
            return RecoveryDecision(
                valid=True,
                allowed=False,
                workflow_id=workflow_id,
                service_name=service_name,
                recommendation="MANUAL_INTERVENTION",
                state=state,
                incident=incident,
                audit_entries=tuple(audits),
                rejection_reasons=(restart.failure_message or "RESTART_REJECTED",),
            )

        last_restart = restart
        for attempt in range(1, self.policy.workflow.maximum_recovery_attempts + 1):
            action = RecoveryAction(
                action_id=self._id(
                    "action", f"{workflow_id}:restart:{attempt}"
                ),
                action_type="SERVICE_RESTART",
                service_name=service_name,
                requested_at=datetime.now(timezone.utc).isoformat(),
                attempt_number=attempt,
            )
            actions.append(action)
            last_restart = self.restart_engine.execute(
                restart,
                restart_callable=restart_callable,
            )
            self.repository.save_restart(last_restart)
            audit(
                "RESTART_EXECUTION",
                last_restart.status,
                {"attempt": attempt},
            )
            if last_restart.status != "COMPLETED":
                continue

            verified = bool(health_verifier())
            audit(
                "POST_RECOVERY_HEALTH_CHECK",
                "SUCCESS" if verified else "FAILED",
                {"attempt": attempt},
            )
            if verified:
                state = replace(
                    state,
                    status="COMPLETED",
                    current_step="VERIFIED",
                    attempt_count=attempt,
                    actions=tuple(actions),
                    restart_record=last_restart,
                    completed_at=datetime.now(timezone.utc).isoformat(),
                    updated_at=datetime.now(timezone.utc).isoformat(),
                    version=state.version + 1,
                )
                self.repository.save_workflow(state)
                return RecoveryDecision(
                    valid=True,
                    allowed=True,
                    workflow_id=workflow_id,
                    service_name=service_name,
                    recommendation="RECOVERED",
                    state=state,
                    audit_entries=tuple(audits),
                )

        incident = self.incident_engine.open_incident(
            service_name=service_name,
            environment=environment,
            title=f"Automatic recovery exhausted for {service_name}",
            critical=critical,
            workflow_id=workflow_id,
            metadata={
                "attempts": self.policy.workflow.maximum_recovery_attempts
            },
        )
        self.repository.save_incident(incident)
        audit("INCIDENT_OPENED", "SUCCESS", {
            "incident_id": incident.incident_id
        })
        state = replace(
            state,
            status="FAILED",
            current_step="INCIDENT_OPENED",
            attempt_count=self.policy.workflow.maximum_recovery_attempts,
            actions=tuple(actions),
            restart_record=last_restart,
            incident=incident,
            failure_reason="RECOVERY_ATTEMPTS_EXHAUSTED",
            completed_at=datetime.now(timezone.utc).isoformat(),
            updated_at=datetime.now(timezone.utc).isoformat(),
            version=state.version + 1,
        )
        self.repository.save_workflow(state)
        return RecoveryDecision(
            valid=True,
            allowed=False,
            workflow_id=workflow_id,
            service_name=service_name,
            recommendation="INCIDENT_OPENED",
            state=state,
            incident=incident,
            audit_entries=tuple(audits),
            rejection_reasons=("RECOVERY_ATTEMPTS_EXHAUSTED",),
        )
