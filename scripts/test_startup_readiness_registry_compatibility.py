from __future__ import annotations

import json
import tempfile
from pathlib import Path

from trading_ai.config.environment_registry import (
    EnvironmentConfigurationRegistry,
)
from trading_ai.config.startup_readiness_service import (
    StartupReadinessService,
)


def main() -> None:
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        config_dir = root / "config"
        config_dir.mkdir(parents=True)

        registry_path = config_dir / "environment_registry.json"
        registry = EnvironmentConfigurationRegistry(registry_path)
        registered = registry.register(
            "production",
            "prod-v1",
            {"sample": True},
            runtime_score=98.0,
            runtime_grade="A",
            runtime_allowed=True,
        )
        registry.activate(
            "production",
            "prod-v1",
            actor="test",
            reason="compatibility validation",
        )

        service = StartupReadinessService(
            project_root=root,
            environment_registry_path="config/environment_registry.json",
        )
        payload = service._active_environment_profile("PRODUCTION")

        assert payload is not None
        assert payload["active"] is True
        assert payload["version"] == "prod-v1"
        assert payload["allowed"] is True
        assert payload["runtime_allowed"] is True
        assert payload["configuration_fingerprint"] == registered.configuration_hash
        assert payload["configuration_hash"] == registered.configuration_hash
        assert payload["environment"] == "production"

        # Confirm persisted/reloaded registry compatibility.
        reloaded_service = StartupReadinessService(
            project_root=root,
            environment_registry_path="config/environment_registry.json",
        )
        reloaded = reloaded_service._active_environment_profile("production")
        assert reloaded is not None
        assert reloaded["version"] == "prod-v1"
        assert reloaded["allowed"] is True
        assert reloaded["configuration_fingerprint"] == registered.configuration_hash

    print("All startup-readiness registry compatibility assertions passed.")


if __name__ == "__main__":
    main()
