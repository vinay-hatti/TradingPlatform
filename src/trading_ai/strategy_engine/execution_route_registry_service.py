from __future__ import annotations

from pathlib import Path
from typing import Any

from trading_ai.strategy_engine.execution_route_governance_policy import ExecutionRouteGovernancePolicy
from trading_ai.strategy_engine.execution_route_promotion_engine import ExecutionRoutePromotionEngine
from trading_ai.strategy_engine.execution_route_registry import ExecutionRouteRegistry
from trading_ai.strategy_engine.execution_route_registry_profile import ExecutionRoutePromotionProfile, ExecutionRouteRegistryProfile


class ExecutionRouteRegistryService:
    def __init__(self, path: str | Path | None = None, policy: ExecutionRouteGovernancePolicy | None = None, registry: ExecutionRouteRegistry | None = None):
        self.policy = policy or ExecutionRouteGovernancePolicy()
        self.registry = registry or ExecutionRouteRegistry(path)
        self.promotion_engine = ExecutionRoutePromotionEngine(self.policy)

    def register_route(self, version: str, route: Any, **kwargs):
        return self.registry.register(version, route, **kwargs)

    def evaluate_challenger(self, challenger_version: str) -> ExecutionRoutePromotionProfile:
        champion = self.registry.champion()
        challenger = self.registry.get(challenger_version)
        return self.promotion_engine.evaluate(champion, challenger)

    def promote_challenger(self, challenger_version: str, *, actor: str = "SYSTEM") -> ExecutionRoutePromotionProfile:
        profile = self.evaluate_challenger(challenger_version)
        if not profile.allowed:
            return profile
        return self.registry.promote(profile, actor=actor)

    def profile(self) -> ExecutionRouteRegistryProfile:
        return self.registry.profile()
