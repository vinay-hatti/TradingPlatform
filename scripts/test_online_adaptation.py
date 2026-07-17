import json
import tempfile
from pathlib import Path

from trading_ai.strategy_engine.learning_state_registry import LearningStateRegistry
from trading_ai.strategy_engine.online_adaptation_engine import OnlineAdaptationEngine
from trading_ai.strategy_engine.online_adaptation_policy import OnlineAdaptationPolicy
from trading_ai.strategy_engine.online_adaptation_serialization import online_adaptation_to_dict
from trading_ai.strategy_engine.online_adaptation_service import OnlineAdaptationService


def profile(strategy, performance, confidence, stability, observations=100, allowed=True):
    return {"strategy": strategy, "performance_score": performance, "confidence_score": confidence, "stability_score": stability, "observation_count": observations, "allowed": allowed}


def main():
    policy = OnlineAdaptationPolicy(minimum_observations_per_update=20, minimum_confidence_score=50.0, minimum_promotion_score=60.0, minimum_champion_improvement=2.0)
    engine = OnlineAdaptationEngine(policy)
    result = engine.adapt({"IRON_CONDOR": 0.50, "BULL_CALL_SPREAD": 0.50}, [profile("IRON_CONDOR", 60, 70, 75), profile("BULL_CALL_SPREAD", 90, 85, 80)])
    assert result.valid and result.allowed
    weights = result.metadata["weights_after"]
    assert abs(sum(weights.values()) - 1.0) < 1e-9
    assert weights["BULL_CALL_SPREAD"] > 0.50
    assert all(u.absolute_change <= policy.maximum_absolute_weight_change + 1e-9 for u in result.updates)

    rejected = engine.adapt({"IRON_CONDOR": 1.0}, [profile("IRON_CONDOR", 90, 20, 90, observations=5)])
    assert rejected.valid and not rejected.allowed
    assert rejected.rejection_reasons

    payload = online_adaptation_to_dict(result)
    json.dumps(payload)

    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "learning_registry.json"
        registry = LearningStateRegistry(path, policy)
        registry.register("v1", {"A": 0.5, "B": 0.5}, 70.0, status="CHAMPION")
        registry.register("v2", {"A": 0.4, "B": 0.6}, 75.0, status="CHALLENGER", source_version="v1")
        registry.challenger_version = "v2"
        decision = registry.evaluate_promotion()
        assert decision.allowed and decision.improvement == 5.0
        registry.promote("v2")
        assert registry.champion_version == "v2" and registry.active_version == "v2"
        registry.rollback("v1")
        assert registry.active_version == "v1"
        loaded = LearningStateRegistry(path, policy)
        assert loaded.active_version == "v1"
        assert len(loaded.profile().versions) == 2

        service = OnlineAdaptationService(policy, Path(tmp) / "service_registry.json")
        service.registry.register("base", {"IRON_CONDOR": .5, "BULL_CALL_SPREAD": .5}, 65.0, status="CHAMPION")
        adaptation, state = service.evaluate_and_register({"IRON_CONDOR": .5, "BULL_CALL_SPREAD": .5}, [profile("IRON_CONDOR", 65, 70, 75), profile("BULL_CALL_SPREAD", 90, 90, 85)], "candidate")
        assert state.status == "CHALLENGER" and adaptation.valid

    print("All online-adaptation and learning-state registry assertions passed.")


if __name__ == "__main__":
    main()
