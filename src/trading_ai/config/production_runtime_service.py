from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from .production_configuration import ProductionConfigurationLoader
from .production_runtime_engine import ProductionRuntimeSafetyEngine
from .production_runtime_policy import ProductionRuntimePolicy
from .production_runtime_profile import ProductionRuntimeProfile
from .secret_provider import EnvironmentSecretProvider, SecretProvider


class ProductionRuntimeSafetyService:
    def __init__(
        self,
        project_root: str | Path | None = None,
        policy: ProductionRuntimePolicy | None = None,
        secret_provider: SecretProvider | None = None,
    ) -> None:
        self.loader = ProductionConfigurationLoader(project_root)
        self.engine = ProductionRuntimeSafetyEngine(policy)
        self.secret_provider = secret_provider or EnvironmentSecretProvider()

    def evaluate(
        self,
        environment: str | None = None,
        base_file: str = "config/runtime.json",
    ) -> ProductionRuntimeProfile:
        profile = self.loader.load(environment=environment, base_file=base_file)
        raw: Mapping[str, Any] = {}
        path = self.loader.project_root / base_file
        if path.exists():
            payload = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(payload, dict):
                raw = payload
        return self.engine.evaluate(
            configuration=profile,
            secret_provider=self.secret_provider,
            raw_configuration=raw,
        )

    def assert_startup_allowed(
        self,
        environment: str | None = None,
        base_file: str = "config/runtime.json",
    ) -> ProductionRuntimeProfile:
        profile = self.evaluate(environment=environment, base_file=base_file)
        if not profile.allowed:
            reasons = ", ".join(profile.rejection_reasons) or "UNKNOWN"
            raise RuntimeError(f"Runtime startup blocked: {reasons}")
        return profile
