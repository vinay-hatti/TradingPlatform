from pathlib import Path
from typing import Any, Iterable

from .learning_state_registry import LearningStateRegistry
from .online_adaptation_engine import OnlineAdaptationEngine
from .online_adaptation_policy import OnlineAdaptationPolicy


class OnlineAdaptationService:
    def __init__(self, policy: OnlineAdaptationPolicy | None = None, registry_path: str | Path | None = None):
        self.policy = policy or OnlineAdaptationPolicy()
        self.engine = OnlineAdaptationEngine(self.policy)
        self.registry = LearningStateRegistry(registry_path, self.policy)

    def evaluate_and_register(self, current_weights: dict[str, float], learning_profiles: Iterable[Any], version: str, actor: str = "system"):
        adaptation = self.engine.adapt(current_weights, learning_profiles)
        weights = dict(adaptation.metadata.get("weights_after", current_weights))
        state = self.registry.register(version, weights, adaptation.adaptation_score, status="CHALLENGER", source_version=self.registry.active_version, actor=actor, reason=adaptation.recommendation, metadata={"allowed": adaptation.allowed, "grade": adaptation.grade})
        self.registry.challenger_version = version
        self.registry.save()
        return adaptation, state

    def promote_if_allowed(self, challenger_version: str | None = None, actor: str = "system"):
        decision = self.registry.evaluate_promotion(challenger_version)
        if decision.allowed and self.policy.allow_automatic_promotion:
            self.registry.promote(challenger_version, actor=actor)
        return decision
