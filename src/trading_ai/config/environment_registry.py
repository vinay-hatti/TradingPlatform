from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any, Mapping

from .environment_profile import EnvironmentProfile, EnvironmentRegistryProfile


def stable_configuration_hash(configuration: Mapping[str, Any]) -> str:
    payload = json.dumps(configuration, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class EnvironmentConfigurationRegistry:
    def __init__(self, path: str | Path = "config/environment_registry.json") -> None:
        self.path = Path(path)
        self._environments: dict[str, list[EnvironmentProfile]] = {}
        self._active_versions: dict[str, str] = {}
        self._promotion_history: list[dict[str, Any]] = []
        if self.path.exists():
            self.load()

    def register(
        self,
        environment: str,
        version: str,
        configuration: Mapping[str, Any],
        *,
        runtime_score: float = 0.0,
        runtime_grade: str = "N/A",
        runtime_allowed: bool = False,
        created_by: str = "system",
        source_environment: str | None = None,
        status: str = "CANDIDATE",
        metadata: Mapping[str, Any] | None = None,
    ) -> EnvironmentProfile:
        environment = environment.strip().lower()
        version = version.strip()
        if not environment or not version:
            raise ValueError("environment and version are required")
        if any(p.version == version for p in self._environments.get(environment, [])):
            raise ValueError(f"Duplicate environment version: {environment}:{version}")
        snapshot = json.loads(json.dumps(dict(configuration), default=str))
        profile = EnvironmentProfile(
            name=environment,
            version=version,
            status=status.upper(),
            configuration=snapshot,
            configuration_hash=stable_configuration_hash(snapshot),
            runtime_score=float(runtime_score),
            runtime_grade=str(runtime_grade),
            runtime_allowed=bool(runtime_allowed),
            created_by=created_by,
            source_environment=source_environment,
            metadata=dict(metadata or {}),
        )
        self._environments.setdefault(environment, []).append(profile)
        self.save()
        return profile

    def versions(self, environment: str) -> tuple[EnvironmentProfile, ...]:
        return tuple(self._environments.get(environment.lower(), ()))

    def get(self, environment: str, version: str) -> EnvironmentProfile | None:
        return next((p for p in self.versions(environment) if p.version == version), None)

    def active(self, environment: str) -> EnvironmentProfile | None:
        version = self._active_versions.get(environment.lower())
        return self.get(environment, version) if version else None

    def activate(self, environment: str, version: str, *, actor: str = "system", reason: str = "") -> EnvironmentProfile:
        profile = self.get(environment, version)
        if profile is None:
            raise KeyError(f"Unknown environment version: {environment}:{version}")
        self._active_versions[environment.lower()] = version
        self._promotion_history.append({
            "action": "ACTIVATE",
            "environment": environment.lower(),
            "version": version,
            "actor": actor,
            "reason": reason,
        })
        self.save()
        return profile

    def record_promotion(self, payload: Mapping[str, Any]) -> None:
        self._promotion_history.append(dict(payload))
        self.save()

    def profile(self) -> EnvironmentRegistryProfile:
        return EnvironmentRegistryProfile(
            environments={k: tuple(v) for k, v in self._environments.items()},
            active_versions=dict(self._active_versions),
            promotion_history=tuple(self._promotion_history),
            metadata={"path": str(self.path)},
        )

    def save(self) -> Path:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = self.profile().to_dict()
        self.path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
        return self.path

    def load(self) -> EnvironmentRegistryProfile:
        payload = json.loads(self.path.read_text(encoding="utf-8"))
        self._environments = {
            env: [EnvironmentProfile(**item) for item in items]
            for env, items in payload.get("environments", {}).items()
        }
        self._active_versions = dict(payload.get("active_versions", {}))
        self._promotion_history = list(payload.get("promotion_history", []))
        return self.profile()
