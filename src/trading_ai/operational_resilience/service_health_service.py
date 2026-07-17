from __future__ import annotations

from datetime import datetime

from .runtime_health_registry import JsonRuntimeHealthRegistry
from .service_health_engine import ServiceHealthEngine
from .service_health_policy import ServiceHealthPolicy
from .service_health_profile import (
    DependencyHealth,
    RuntimeHealthDecision,
    ServiceHeartbeat,
)


class ServiceHealthService:
    def __init__(
        self,
        *,
        policy: ServiceHealthPolicy | None = None,
        registry: JsonRuntimeHealthRegistry | None = None,
    ) -> None:
        self.policy = policy or ServiceHealthPolicy()
        self.engine = ServiceHealthEngine(self.policy)
        self.registry = registry or JsonRuntimeHealthRegistry()

    def evaluate_and_publish(
        self,
        *,
        registry_id: str,
        environment: str,
        heartbeats: tuple[ServiceHeartbeat, ...],
        dependencies_by_service: dict[
            str,
            tuple[DependencyHealth, ...],
        ] | None = None,
        as_of: datetime | None = None,
    ) -> RuntimeHealthDecision:
        previous = self.registry.get(registry_id)
        decision = self.engine.evaluate(
            registry_id=registry_id,
            environment=environment,
            heartbeats=heartbeats,
            dependencies_by_service=dependencies_by_service,
            previous_state=previous,
            as_of=as_of,
        )
        if (
            decision.state is not None
            and self.policy.persist_runtime_health
        ):
            self.registry.save(decision.state)
        return decision
