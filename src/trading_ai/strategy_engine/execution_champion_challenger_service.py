from __future__ import annotations

from dataclasses import replace
from typing import Any

from trading_ai.strategy_engine.execution_champion_challenger_engine import ExecutionChampionChallengerEngine
from trading_ai.strategy_engine.execution_champion_challenger_policy import ExecutionChampionChallengerPolicy
from trading_ai.strategy_engine.execution_champion_challenger_profile import (
    ExecutionChampionChallengerBatchProfile,
    ExecutionChampionChallengerProfile,
)


class ExecutionChampionChallengerService:
    """Orchestrates route-registry comparison and controlled promotion."""

    def __init__(self, policy: ExecutionChampionChallengerPolicy | None = None, engine: ExecutionChampionChallengerEngine | None = None):
        self.policy = policy or ExecutionChampionChallengerPolicy()
        self.engine = engine or ExecutionChampionChallengerEngine(self.policy)

    def evaluate(self, champion: Any, challenger: Any) -> ExecutionChampionChallengerProfile:
        return self.engine.evaluate(champion, challenger)

    def evaluate_registry(self, registry: Any) -> ExecutionChampionChallengerBatchProfile:
        champion = registry.champion()
        challengers = [item for item in registry.list_versions() if bool(item.get("challenger")) and not bool(item.get("champion"))]
        return self.engine.evaluate_batch(champion, challengers)

    def evaluate_version(self, registry: Any, challenger_version: str) -> ExecutionChampionChallengerProfile:
        return self.engine.evaluate(registry.champion(), registry.get(challenger_version))

    def promote(self, registry: Any, challenger_version: str, *, actor: str = "SYSTEM") -> ExecutionChampionChallengerProfile:
        profile = self.evaluate_version(registry, challenger_version)
        if not profile.allowed:
            return profile
        if not hasattr(registry, "promote"):
            return replace(profile, warnings=profile.warnings + ("Registry does not support controlled promotion.",))

        try:
            from trading_ai.strategy_engine.execution_route_registry_profile import ExecutionRoutePromotionProfile

            compatible = ExecutionRoutePromotionProfile(
                valid=profile.valid,
                allowed=profile.allowed,
                route_type=profile.route_type,
                champion_version=profile.champion_version,
                challenger_version=profile.challenger_version,
                champion_route_name=profile.champion_route_name,
                challenger_route_name=profile.challenger_route_name,
                champion_route_score=profile.route_score_improvement + 0.0,
                challenger_route_score=profile.route_score_improvement + 0.0,
                route_score_improvement=profile.route_score_improvement,
                shortfall_improvement_bps=profile.shortfall_improvement_bps,
                fill_ratio_change=profile.fill_ratio_change,
                latency_change_seconds=profile.latency_change_seconds,
                spread_change_bps=profile.spread_change_bps,
                champion_governance_score=profile.champion_governance_score,
                challenger_governance_score=profile.challenger_governance_score,
                promotion_score=profile.evaluation_score,
                promotion_grade=profile.evaluation_grade,
                promotion_severity=profile.governance_severity,
                recommendation=profile.recommendation,
                warnings=profile.warnings,
                rejection_reasons=profile.rejection_reasons,
                metadata=profile.metadata,
            )
            registry.promote(compatible, actor=actor)
            return replace(profile, promoted=True, recommendation="PROMOTED")
        except ImportError:
            return replace(profile, warnings=profile.warnings + ("Step 5.2 route-registry package is unavailable.",))
