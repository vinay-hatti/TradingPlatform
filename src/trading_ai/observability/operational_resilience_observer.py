from __future__ import annotations

from typing import Any

from .observability_profile import ObservabilityContext
from .observability_service import ObservabilityService
from .runtime_metrics_collector import RuntimeMetricsCollector


class OperationalResilienceObserver:
    """Translate Phase 8 outcomes into logs, metrics, and traces."""

    def __init__(
        self,
        *,
        observability: ObservabilityService,
        metrics: RuntimeMetricsCollector,
    ) -> None:
        self.observability = observability
        self.metrics = metrics

    def _log(
        self,
        *,
        level: str,
        event_name: str,
        message: str,
        service_name: str,
        environment: str,
        fields: dict[str, Any],
    ) -> None:
        context = ObservabilityContext(
            service_name=service_name,
            environment=environment,
            component="operational_resilience",
            operation=event_name,
        )
        record = self.observability.logging.create_record(
            level=level,
            message=message,
            context=context,
            event_name=event_name,
            fields=fields,
        )
        if record is not None:
            self.observability.logging.serialize(record)

    def observe_runtime_health(self, decision: Any) -> None:
        self.metrics.observe_runtime_health(decision)
        level = "INFO" if getattr(decision, "allowed", False) else "ERROR"
        self._log(
            level=level,
            event_name="runtime_health.evaluated",
            message="Runtime health evaluation completed",
            service_name="runtime-health-registry",
            environment=str(
                getattr(decision, "environment", "unknown")
            ),
            fields={
                "allowed": getattr(decision, "allowed", False),
                "score": getattr(decision, "score", 0.0),
                "recommendation": getattr(
                    decision, "recommendation", "UNKNOWN"
                ),
            },
        )

    def observe_resilience_execution(self, decision: Any) -> None:
        circuit = getattr(decision, "circuit_state", None)
        bulkhead = getattr(decision, "bulkhead_state", None)
        if circuit is not None:
            self.metrics.observe_circuit(circuit)
        if bulkhead is not None:
            self.metrics.observe_bulkhead(bulkhead)
        self._log(
            level="INFO" if getattr(decision, "allowed", False) else "WARNING",
            event_name="resilience_execution.completed",
            message="Resilience execution completed",
            service_name=str(
                getattr(decision, "dependency_name", "dependency")
            ),
            environment="unknown",
            fields={
                "operation_id": getattr(
                    decision, "operation_id", None
                ),
                "recommendation": getattr(
                    decision, "recommendation", "UNKNOWN"
                ),
                "rejection_reasons": getattr(
                    decision, "rejection_reasons", ()
                ),
            },
        )

    def observe_recovery(self, decision: Any) -> None:
        self.metrics.observe_recovery(decision)
        incident = getattr(decision, "incident", None)
        if incident is not None:
            self.metrics.observe_incident(incident)
        state = getattr(decision, "state", None)
        self._log(
            level="INFO" if getattr(decision, "allowed", False) else "ERROR",
            event_name="recovery_workflow.completed",
            message="Recovery workflow completed",
            service_name=str(
                getattr(decision, "service_name", "recovery")
            ),
            environment=str(
                getattr(state, "environment", "unknown")
            ),
            fields={
                "workflow_id": getattr(
                    decision, "workflow_id", None
                ),
                "recommendation": getattr(
                    decision, "recommendation", "UNKNOWN"
                ),
                "incident_id": getattr(
                    incident, "incident_id", None
                ) if incident else None,
            },
        )

    def observe_watchdog(self, decision: Any) -> None:
        self.metrics.observe_watchdog(decision)
        cycle = getattr(decision, "cycle_state", None)
        self._log(
            level="INFO" if getattr(decision, "allowed", False) else "ERROR",
            event_name="watchdog_cycle.completed",
            message="Operational watchdog cycle completed",
            service_name="operational-watchdog",
            environment=str(
                getattr(decision, "environment", "unknown")
            ),
            fields={
                "cycle_id": getattr(decision, "cycle_id", None),
                "status": getattr(cycle, "status", "UNKNOWN"),
                "recommendation": getattr(
                    decision, "recommendation", "UNKNOWN"
                ),
                "alert_count": getattr(cycle, "alert_count", 0),
                "incident_count": getattr(
                    cycle, "incident_count", 0
                ),
                "recovery_count": getattr(
                    cycle, "recovery_count", 0
                ),
            },
        )
