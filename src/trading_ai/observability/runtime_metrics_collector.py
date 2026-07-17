from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .instrumentation_policy import RuntimeMetricsCollectionPolicy
from .metrics_registry import MetricsRegistry
from .observability_profile import MetricDefinition


class RuntimeMetricsCollector:
    def __init__(
        self,
        *,
        registry: MetricsRegistry,
        policy: RuntimeMetricsCollectionPolicy | None = None,
        metric_prefix: str = "trading_ai",
    ) -> None:
        self.registry = registry
        self.policy = policy or RuntimeMetricsCollectionPolicy()
        self.metric_prefix = metric_prefix
        self.started_at = datetime.now(timezone.utc)
        self._register_defaults()

    def _register_defaults(self) -> None:
        definitions = (
            MetricDefinition(
                name=f"{self.metric_prefix}_runtime_uptime_seconds",
                metric_type="GAUGE",
                description="Runtime process uptime.",
                unit="seconds",
                label_names=("environment", "service"),
            ),
            MetricDefinition(
                name=f"{self.metric_prefix}_runtime_health_score",
                metric_type="GAUGE",
                description="Aggregated runtime health score.",
                unit="score",
                label_names=("environment",),
            ),
            MetricDefinition(
                name=f"{self.metric_prefix}_service_ready",
                metric_type="GAUGE",
                description="Service readiness indicator.",
                unit="1",
                label_names=("environment", "service", "instance"),
            ),
            MetricDefinition(
                name=f"{self.metric_prefix}_circuit_open",
                metric_type="GAUGE",
                description="Circuit breaker open indicator.",
                unit="1",
                label_names=("dependency",),
            ),
            MetricDefinition(
                name=f"{self.metric_prefix}_bulkhead_active_calls",
                metric_type="GAUGE",
                description="Active calls in a dependency bulkhead.",
                unit="calls",
                label_names=("dependency",),
            ),
            MetricDefinition(
                name=f"{self.metric_prefix}_recovery_workflows_total",
                metric_type="COUNTER",
                description="Observed recovery workflow outcomes.",
                unit="workflows",
                label_names=("environment", "service", "status"),
            ),
            MetricDefinition(
                name=f"{self.metric_prefix}_incidents_total",
                metric_type="COUNTER",
                description="Observed incident records.",
                unit="incidents",
                label_names=("environment", "severity", "status"),
            ),
            MetricDefinition(
                name=f"{self.metric_prefix}_watchdog_cycles_total",
                metric_type="COUNTER",
                description="Observed watchdog cycle outcomes.",
                unit="cycles",
                label_names=("environment", "status", "recommendation"),
            ),
        )
        for definition in definitions:
            try:
                self.registry.register(definition)
            except ValueError:
                pass

    def collect_uptime(
        self,
        *,
        environment: str,
        service: str,
    ) -> None:
        if not self.policy.collect_process_uptime:
            return
        seconds = (
            datetime.now(timezone.utc) - self.started_at
        ).total_seconds()
        self.registry.record(
            name=f"{self.metric_prefix}_runtime_uptime_seconds",
            value=seconds,
            labels={
                "environment": environment,
                "service": service,
            },
        )

    def observe_runtime_health(self, decision: Any) -> None:
        if self.policy.collect_health_score:
            self.registry.record(
                name=f"{self.metric_prefix}_runtime_health_score",
                value=float(getattr(decision, "score", 0.0)),
                labels={
                    "environment": str(
                        getattr(decision, "environment", "unknown")
                    )
                },
            )
        state = getattr(decision, "state", None)
        if (
            self.policy.collect_service_readiness
            and state is not None
        ):
            for service in getattr(state, "services", ()):
                self.registry.record(
                    name=f"{self.metric_prefix}_service_ready",
                    value=1.0 if service.ready else 0.0,
                    labels={
                        "environment": str(state.environment),
                        "service": str(service.service_name),
                        "instance": str(service.instance_id),
                    },
                )

    def observe_circuit(self, state: Any) -> None:
        if not self.policy.collect_circuit_state:
            return
        self.registry.record(
            name=f"{self.metric_prefix}_circuit_open",
            value=1.0 if getattr(state, "state", "") == "OPEN" else 0.0,
            labels={
                "dependency": str(
                    getattr(state, "dependency_name", "unknown")
                )
            },
        )

    def observe_bulkhead(self, state: Any) -> None:
        if not self.policy.collect_bulkhead_state:
            return
        self.registry.record(
            name=f"{self.metric_prefix}_bulkhead_active_calls",
            value=float(getattr(state, "active_calls", 0)),
            labels={
                "dependency": str(
                    getattr(state, "dependency_name", "unknown")
                )
            },
        )

    def observe_recovery(self, decision: Any) -> None:
        if not self.policy.collect_recovery_state:
            return
        state = getattr(decision, "state", None)
        if state is None:
            return
        self.registry.record(
            name=f"{self.metric_prefix}_recovery_workflows_total",
            value=1,
            labels={
                "environment": str(state.environment),
                "service": str(state.service_name),
                "status": str(state.status),
            },
        )

    def observe_incident(self, incident: Any) -> None:
        if not self.policy.collect_incident_state:
            return
        self.registry.record(
            name=f"{self.metric_prefix}_incidents_total",
            value=1,
            labels={
                "environment": str(
                    getattr(incident, "environment", "unknown")
                ),
                "severity": str(
                    getattr(incident, "severity", "UNKNOWN")
                ),
                "status": str(
                    getattr(incident, "status", "UNKNOWN")
                ),
            },
        )

    def observe_watchdog(self, decision: Any) -> None:
        if not self.policy.collect_watchdog_state:
            return
        cycle = getattr(decision, "cycle_state", None)
        if cycle is None:
            return
        self.registry.record(
            name=f"{self.metric_prefix}_watchdog_cycles_total",
            value=1,
            labels={
                "environment": str(cycle.environment),
                "status": str(cycle.status),
                "recommendation": str(cycle.recommendation),
            },
        )
