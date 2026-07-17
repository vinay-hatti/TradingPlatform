from __future__ import annotations
from dataclasses import replace
from datetime import datetime, timezone
import hashlib
from typing import Callable

from .health_alert_router import HealthAlertRouter
from .incident_escalation_engine import IncidentEscalationEngine
from .recovery_profile import IncidentRecord
from .recovery_repository import JsonRecoveryRepository
from .recovery_workflow_engine import RecoveryWorkflowEngine
from .service_health_profile import RuntimeHealthDecision
from .watchdog_policy import WatchdogGovernancePolicy
from .watchdog_profile import WatchdogCycleState, WatchdogDecision
from .watchdog_repository import JsonWatchdogRepository

class OperationalWatchdogService:
    def __init__(
        self,
        *,
        policy: WatchdogGovernancePolicy | None = None,
        watchdog_repository: JsonWatchdogRepository | None = None,
        recovery_repository: JsonRecoveryRepository | None = None,
        recovery_engine: RecoveryWorkflowEngine | None = None,
    ) -> None:
        self.policy = policy or WatchdogGovernancePolicy()
        self.policy.validate()
        self.watchdog_repository = (
            watchdog_repository or JsonWatchdogRepository()
        )
        self.recovery_repository = (
            recovery_repository or JsonRecoveryRepository()
        )
        self.alert_router = HealthAlertRouter(
            policy=self.policy.alerts,
            repository=self.watchdog_repository,
        )
        self.escalation_engine = IncidentEscalationEngine(
            self.policy.escalation
        )
        self.recovery_engine = recovery_engine or RecoveryWorkflowEngine(
            repository=self.recovery_repository
        )

    @staticmethod
    def _cycle_id(environment: str, sequence: int, at: str) -> str:
        raw = f"{environment}:{sequence}:{at}"
        return "watchdog-" + hashlib.sha256(raw.encode()).hexdigest()[:16]

    def run_cycle(
        self,
        *,
        environment: str,
        health_decision: RuntimeHealthDecision,
        restart_callable_factory: Callable[[str], Callable[[], bool]],
        health_verifier_factory: Callable[[str], Callable[[], bool]],
        as_of: datetime | None = None,
    ) -> WatchdogDecision:
        now = as_of or datetime.now(timezone.utc)
        previous = self.watchdog_repository.latest_cycle(environment)
        sequence = (previous.sequence_number + 1) if previous else 1
        cycle = WatchdogCycleState(
            cycle_id=self._cycle_id(
                environment, sequence, now.isoformat()
            ),
            environment=environment,
            sequence_number=sequence,
            status="RUNNING",
            recommendation="MONITOR",
            health_registry_id=health_decision.registry_id,
            health_allowed=health_decision.allowed,
            health_score=health_decision.score,
            started_at=now.isoformat(),
        )
        self.watchdog_repository.save_cycle(cycle)

        alerts = []
        escalations = []
        recovery_ids = []
        incident_ids = []
        warnings = list(health_decision.warnings)
        rejection_reasons = list(health_decision.rejection_reasons)

        try:
            unhealthy_services = ()
            if health_decision.state is not None:
                unhealthy_services = tuple(
                    service
                    for service in health_decision.state.services
                    if not service.healthy
                )

            for service in unhealthy_services:
                severity = (
                    "CRITICAL"
                    if service.critical and not service.ready
                    else "SEVERE"
                )
                alert = self.alert_router.route(
                    service_name=service.service_name,
                    environment=environment,
                    severity=severity,
                    title=f"Runtime health degradation: {service.service_name}",
                    message=(
                        f"status={service.status}; score={service.score}; "
                        f"warnings={','.join(service.warnings)}"
                    ),
                    metadata={
                        "registry_id": health_decision.registry_id,
                        "cycle_id": cycle.cycle_id,
                    },
                    as_of=now,
                )
                alerts.append(alert)

                should_recover = (
                    self.policy.watchdog.invoke_recovery_on_not_ready
                    and not service.ready
                ) or (
                    self.policy.watchdog.invoke_recovery_on_critical_health
                    and severity == "CRITICAL"
                )
                if should_recover:
                    recovery = self.recovery_engine.execute(
                        service_name=service.service_name,
                        instance_id=service.instance_id,
                        environment=environment,
                        trigger="watchdog-health-failure",
                        critical=service.critical,
                        restart_callable=restart_callable_factory(
                            service.service_name
                        ),
                        health_verifier=health_verifier_factory(
                            service.service_name
                        ),
                    )
                    recovery_ids.append(recovery.workflow_id)
                    if recovery.incident is not None:
                        incident_ids.append(recovery.incident.incident_id)
                        linked = replace(
                            alert,
                            incident_id=recovery.incident.incident_id,
                        )
                        self.watchdog_repository.save_alert(linked)
                        alerts[-1] = linked
                        existing = (
                            self.watchdog_repository.escalations_for_incident(
                                recovery.incident.incident_id
                            )
                        )
                        escalation = self.escalation_engine.next_escalation(
                            incident=recovery.incident,
                            existing=existing,
                            as_of=now,
                        )
                        if escalation:
                            self.watchdog_repository.save_escalation(
                                escalation
                            )
                            escalations.append(escalation)

            allowed = health_decision.allowed and not incident_ids
            recommendation = (
                "MONITOR"
                if allowed and not alerts
                else "DEGRADED_MONITOR"
                if allowed
                else "RECOVERY_REQUIRED"
            )
            cycle = replace(
                cycle,
                status="COMPLETED",
                recommendation=recommendation,
                alert_count=len(alerts),
                incident_count=len(incident_ids),
                escalation_count=len(escalations),
                recovery_count=len(recovery_ids),
                completed_at=datetime.now(timezone.utc).isoformat(),
            )
            self.watchdog_repository.save_cycle(cycle)
            return WatchdogDecision(
                valid=True,
                allowed=allowed,
                environment=environment,
                cycle_id=cycle.cycle_id,
                recommendation=recommendation,
                cycle_state=cycle,
                alerts=tuple(alerts),
                escalations=tuple(escalations),
                recovery_workflow_ids=tuple(recovery_ids),
                incident_ids=tuple(incident_ids),
                warnings=tuple(dict.fromkeys(warnings)),
                rejection_reasons=tuple(dict.fromkeys(rejection_reasons)),
                metadata={
                    "health_recommendation": health_decision.recommendation,
                },
            )
        except BaseException as exc:
            cycle = replace(
                cycle,
                status="FAILED",
                recommendation="FAIL_CLOSED",
                failed_stage="WATCHDOG_ORCHESTRATION",
                error=f"{type(exc).__name__}:{exc}",
                completed_at=datetime.now(timezone.utc).isoformat(),
            )
            self.watchdog_repository.save_cycle(cycle)
            return WatchdogDecision(
                valid=False,
                allowed=False,
                environment=environment,
                cycle_id=cycle.cycle_id,
                recommendation="FAIL_CLOSED",
                cycle_state=cycle,
                alerts=tuple(alerts),
                escalations=tuple(escalations),
                recovery_workflow_ids=tuple(recovery_ids),
                incident_ids=tuple(incident_ids),
                warnings=tuple(dict.fromkeys(warnings)),
                rejection_reasons=(
                    "WATCHDOG_ORCHESTRATION_FAILED",
                ),
                metadata={"error": cycle.error},
            )
