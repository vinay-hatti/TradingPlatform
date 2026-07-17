from __future__ import annotations

from dataclasses import asdict, replace
from pathlib import Path
from typing import Any, Mapping

from .environment_profile import EnvironmentProfile, EnvironmentPromotionProfile
from .environment_promotion_engine import EnvironmentPromotionEngine
from .environment_registry import EnvironmentConfigurationRegistry
from .environment_registry_policy import EnvironmentRegistryPolicy


class EnvironmentRegistryService:
    def __init__(
        self,
        registry_path: str | Path = "config/environment_registry.json",
        policy: EnvironmentRegistryPolicy | None = None,
    ) -> None:
        self.registry = EnvironmentConfigurationRegistry(registry_path)
        self.engine = EnvironmentPromotionEngine(policy)

    def register_runtime_profile(
        self,
        environment: str,
        version: str,
        configuration: Mapping[str, Any],
        runtime_profile: Any,
        *,
        actor: str = "system",
        source_environment: str | None = None,
    ) -> EnvironmentProfile:
        return self.registry.register(
            environment,
            version,
            configuration,
            runtime_score=float(getattr(runtime_profile, "score", 0.0)),
            runtime_grade=str(getattr(runtime_profile, "grade", "N/A")),
            runtime_allowed=bool(getattr(runtime_profile, "allowed", False)),
            created_by=actor,
            source_environment=source_environment,
            metadata={"runtime_recommendation": getattr(runtime_profile, "recommendation", None)},
        )

    def evaluate_promotion(
        self,
        source_environment: str,
        source_version: str,
        target_environment: str,
        *,
        target_runtime_score: float | None,
        target_runtime_allowed: bool | None,
        manual_approval: bool = False,
    ) -> EnvironmentPromotionProfile:
        source = self.registry.get(source_environment, source_version)
        if source is None:
            raise KeyError(f"Unknown source profile: {source_environment}:{source_version}")
        return self.engine.evaluate(
            source,
            target_environment,
            target_runtime_score=target_runtime_score,
            target_runtime_allowed=target_runtime_allowed,
            manual_approval=manual_approval,
        )

    def promote(
        self,
        source_environment: str,
        source_version: str,
        target_environment: str,
        target_version: str,
        *,
        target_runtime_score: float,
        target_runtime_allowed: bool,
        manual_approval: bool = False,
        actor: str = "system",
        reason: str = "",
    ) -> tuple[EnvironmentProfile, EnvironmentPromotionProfile]:
        evaluation = self.evaluate_promotion(
            source_environment,
            source_version,
            target_environment,
            target_runtime_score=target_runtime_score,
            target_runtime_allowed=target_runtime_allowed,
            manual_approval=manual_approval,
        )
        if not evaluation.allowed:
            raise RuntimeError("Environment promotion rejected: " + ", ".join(evaluation.rejection_reasons))
        source = self.registry.get(source_environment, source_version)
        assert source is not None
        target = self.registry.register(
            target_environment,
            target_version,
            source.configuration,
            runtime_score=target_runtime_score,
            runtime_grade="A" if target_runtime_score >= 95 else "B",
            runtime_allowed=target_runtime_allowed,
            created_by=actor,
            source_environment=source_environment,
            status="PROMOTED",
            metadata={"source_version": source_version, "reason": reason},
        )
        self.registry.activate(target_environment, target_version, actor=actor, reason=reason)
        completed = replace(evaluation, target_version=target_version)
        self.registry.record_promotion({
            "action": "PROMOTE",
            "actor": actor,
            "reason": reason,
            "evaluation": asdict(completed),
        })
        return target, completed
