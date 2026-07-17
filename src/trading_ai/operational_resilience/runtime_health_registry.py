from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from .service_health_profile import (
    DependencyHealth,
    RuntimeHealthState,
    ServiceHealthSnapshot,
)


class JsonRuntimeHealthRegistry:
    """Atomic, versioned persistence for runtime health states."""

    def __init__(
        self,
        path: str | Path = (
            "data/operational_resilience/runtime_health_registry.json"
        ),
    ) -> None:
        self.path = Path(path)

    def _load(self) -> dict[str, RuntimeHealthState]:
        if not self.path.exists():
            return {}
        payload = json.loads(self.path.read_text(encoding="utf-8"))
        result: dict[str, RuntimeHealthState] = {}
        for registry_id, raw in payload.get("registries", {}).items():
            item = dict(raw)
            services = []
            for service in item.get("services", ()):
                service = dict(service)
                service["dependencies"] = tuple(
                    DependencyHealth(**dependency)
                    for dependency in service.get("dependencies", ())
                )
                services.append(ServiceHealthSnapshot(**service))
            item["services"] = tuple(services)
            result[registry_id] = RuntimeHealthState(**item)
        return result

    def _save(self, states: dict[str, RuntimeHealthState]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(self.path.suffix + ".tmp")
        temporary.write_text(
            json.dumps(
                {
                    "registries": {
                        key: asdict(value)
                        for key, value in states.items()
                    }
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        temporary.replace(self.path)

    def save(self, state: RuntimeHealthState) -> RuntimeHealthState:
        states = self._load()
        states[state.registry_id] = state
        self._save(states)
        return state

    def get(self, registry_id: str) -> RuntimeHealthState | None:
        return self._load().get(registry_id)

    def latest_for_environment(
        self,
        environment: str,
    ) -> RuntimeHealthState | None:
        matches = [
            state
            for state in self._load().values()
            if state.environment == environment
        ]
        if not matches:
            return None
        return max(matches, key=lambda item: item.updated_at)

    def all(self) -> tuple[RuntimeHealthState, ...]:
        return tuple(self._load().values())
