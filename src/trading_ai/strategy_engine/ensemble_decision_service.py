from typing import Any, Iterable

from trading_ai.strategy_engine.ensemble_decision_engine import EnsembleDecisionEngine
from trading_ai.strategy_engine.ensemble_decision_policy import EnsembleDecisionPolicy


class EnsembleDecisionService:
    def __init__(self, policy: EnsembleDecisionPolicy | None = None, engine: EnsembleDecisionEngine | None = None):
        self.engine = engine or EnsembleDecisionEngine(policy)

    def decide(self, symbol: str, strategies: Iterable[str], **sources: Any):
        return self.engine.decide(symbol, strategies, **sources)

    def attach(self, target: Any, profile: Any) -> Any:
        if isinstance(target, dict):
            target["ensemble_decision_profile"] = profile
            target.setdefault("metadata", {})["ensemble_decision_profile"] = profile
            return target
        try:
            setattr(target, "ensemble_decision_profile", profile)
        except Exception:
            metadata = getattr(target, "metadata", None)
            if isinstance(metadata, dict):
                metadata["ensemble_decision_profile"] = profile
        return target
