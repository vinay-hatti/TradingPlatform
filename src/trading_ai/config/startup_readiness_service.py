from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from .environment_registry import EnvironmentConfigurationRegistry
from .production_configuration import ProductionConfigurationLoader
from .production_runtime_service import ProductionRuntimeSafetyService
from .secret_governance_service import SecretGovernanceService
from .secret_provider import EnvironmentSecretProvider, SecretProvider
from .startup_readiness_engine import StartupReadinessEngine
from .startup_readiness_policy import StartupReadinessPolicy
from .startup_readiness_profile import StartupReadinessProfile


def configuration_fingerprint(configuration: Any) -> str:
    """
    Produce the stable fingerprint used by startup-readiness governance.

    Volatile loader metadata and source file names are excluded so the same
    effective configuration produces the same fingerprint across hosts.
    """
    if hasattr(configuration, "to_dict"):
        payload = configuration.to_dict()
    else:
        try:
            payload = asdict(configuration)
        except TypeError:
            payload = dict(configuration)

    payload = dict(payload)
    payload.pop("source_files", None)

    metadata = dict(payload.get("metadata", {}) or {})
    metadata.pop("project_root", None)
    payload["metadata"] = metadata

    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


class StartupReadinessService:
    """
    Aggregate runtime safety, environment registry and secret governance.

    The environment registry adapter intentionally supports both the Step 2
    public methods and older/property-based registry implementations.
    """

    def __init__(
        self,
        project_root: str | Path | None = None,
        *,
        policy: StartupReadinessPolicy | None = None,
        secret_provider: SecretProvider | None = None,
        environment_registry_path: str = "config/environment_registry.json",
        secret_inventory_path: str = "config/secret_inventory.json",
    ) -> None:
        self.project_root = Path(project_root or Path.cwd()).resolve()
        self.policy = policy or StartupReadinessPolicy()
        self.engine = StartupReadinessEngine(self.policy)
        self.secret_provider = secret_provider or EnvironmentSecretProvider()
        self.environment_registry_path = (
            self.project_root / environment_registry_path
        )
        self.secret_inventory_path = self.project_root / secret_inventory_path

    @staticmethod
    def _normalize_environment_name(environment: str) -> str:
        return str(environment or "").strip().lower()

    def _active_environment_profile(self, environment: str) -> Any:
        """
        Return an engine-compatible active environment profile.

        Step 2's EnvironmentConfigurationRegistry exposes active() and stores:
            runtime_allowed
            configuration_hash

        StartupReadinessEngine expects:
            allowed
            configuration_fingerprint

        This adapter maps those fields without changing either established
        contract. It also tolerates earlier registry variants that exposed
        active_versions or _active_versions directly.
        """
        if not self.environment_registry_path.exists():
            return None

        normalized_environment = self._normalize_environment_name(environment)
        registry = EnvironmentConfigurationRegistry(
            self.environment_registry_path
        )

        profile = None
        active_version = None

        active_method = getattr(registry, "active", None)
        if callable(active_method):
            profile = active_method(normalized_environment)
            if profile is not None:
                active_version = getattr(profile, "version", None)

        if profile is None:
            active_versions = getattr(registry, "active_versions", None)
            if active_versions is None:
                active_versions = getattr(registry, "_active_versions", None)

            if isinstance(active_versions, dict):
                active_version = active_versions.get(normalized_environment)

            if active_version:
                get_method = getattr(registry, "get", None)
                if callable(get_method):
                    profile = get_method(
                        normalized_environment,
                        active_version,
                    )

        if profile is None:
            registry_profile_method = getattr(registry, "profile", None)
            if callable(registry_profile_method):
                registry_profile = registry_profile_method()
                profile_active_versions = getattr(
                    registry_profile,
                    "active_versions",
                    {},
                )
                active_version = profile_active_versions.get(
                    normalized_environment
                )
                if active_version:
                    get_method = getattr(registry, "get", None)
                    if callable(get_method):
                        profile = get_method(
                            normalized_environment,
                            active_version,
                        )

        if profile is None:
            return None

        if hasattr(profile, "to_dict"):
            payload = profile.to_dict()
        else:
            try:
                payload = asdict(profile)
            except TypeError:
                payload = dict(profile)

        payload = dict(payload)
        payload["active"] = True

        if not payload.get("version") and active_version:
            payload["version"] = active_version

        # Step 2 -> startup readiness compatibility aliases.
        if "allowed" not in payload:
            payload["allowed"] = bool(
                payload.get("runtime_allowed", False)
            )

        if "configuration_fingerprint" not in payload:
            payload["configuration_fingerprint"] = payload.get(
                "configuration_hash"
            )

        if "environment" not in payload:
            payload["environment"] = payload.get(
                "name",
                normalized_environment,
            )

        return payload

    def evaluate(
        self,
        environment: str | None = None,
        base_file: str = "config/runtime.json",
    ) -> StartupReadinessProfile:
        loader = ProductionConfigurationLoader(self.project_root)
        configuration = loader.load(
            environment=environment,
            base_file=base_file,
        )
        fingerprint = configuration_fingerprint(configuration)

        runtime_service = ProductionRuntimeSafetyService(
            project_root=self.project_root,
            secret_provider=self.secret_provider,
        )
        runtime_profile = runtime_service.evaluate(
            environment=configuration.environment,
            base_file=base_file,
        )

        active_environment = self._active_environment_profile(
            configuration.environment
        )

        secret_profile = None
        if self.secret_inventory_path.exists():
            secret_service = SecretGovernanceService(
                self.secret_inventory_path,
                provider=self.secret_provider,
            )
            secret_profile = secret_service.evaluate_environment(
                configuration.environment
            )

        return self.engine.evaluate(
            environment=configuration.environment,
            configuration_fingerprint=fingerprint,
            runtime_profile=runtime_profile,
            environment_registry_profile=active_environment,
            secret_governance_profile=secret_profile,
        )

    def assert_ready(
        self,
        environment: str | None = None,
        base_file: str = "config/runtime.json",
    ) -> StartupReadinessProfile:
        profile = self.evaluate(
            environment=environment,
            base_file=base_file,
        )
        if not profile.allowed:
            reasons = ", ".join(profile.rejection_reasons) or "UNKNOWN"
            raise RuntimeError(
                f"Startup readiness gate blocked startup: {reasons}"
            )
        return profile
