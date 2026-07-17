from types import SimpleNamespace

from trading_ai.strategy_engine.phase10_decision_integration_policy import Phase10DecisionIntegrationPolicy
from trading_ai.strategy_engine.phase10_decision_integration_service import Phase10DecisionIntegrationService
from trading_ai.strategy_engine.phase10_decision_integration_serialization import phase10_to_dict


def main():
    adaptive = SimpleNamespace(valid=True, allowed=True, selected_strategy="IRON_CONDOR", selected_score=82.0, selection_confidence_score=78.0)
    ensemble = SimpleNamespace(valid=True, allowed=True, selected_strategy="IRON_CONDOR", selected_direction="NEUTRAL", ensemble_score=88.0, meta_confidence_score=84.0, consensus_ratio=0.8)
    registry = SimpleNamespace(active_version="learn-v2", champion_version="learn-v1", challenger_version="learn-v2")
    adaptation = SimpleNamespace(adaptation_score=86.0)
    weighting = SimpleNamespace(weights=(SimpleNamespace(strategy="IRON_CONDOR", normalized_weight=0.42),))
    decision = SimpleNamespace(symbol="SPY", strategy="CALL", direction="BULLISH", allowed=True, rejection_reasons=[], metadata={})

    service = Phase10DecisionIntegrationService(Phase10DecisionIntegrationPolicy(require_ensemble_approval=True, minimum_meta_confidence_score=70.0))
    profiles = service.analyze(
        [decision],
        adaptive_profiles={"SPY": adaptive},
        ensemble_profiles={"SPY": ensemble},
        dynamic_strategy_weighting_profile=weighting,
        online_adaptation_profile=adaptation,
        learning_state_registry_profile=registry,
    )
    service.attach([decision], profiles)
    profile = profiles["SPY"]
    assert profile.valid and profile.allowed
    assert profile.selected_strategy == "IRON_CONDOR"
    assert decision.ensemble_selected_strategy == "IRON_CONDOR"
    assert decision.dynamic_strategy_weight == 0.42
    assert decision.learning_state_version == "learn-v2"
    assert decision.allowed is True
    assert phase10_to_dict(profile)["ensemble_score"] == 88.0

    rejected = SimpleNamespace(symbol="QQQ", strategy="PUT", direction="BEARISH", allowed=True, rejection_reasons=[], metadata={})
    bad = SimpleNamespace(valid=True, allowed=False, selected_strategy="PUT", selected_direction="BEARISH", ensemble_score=55.0, meta_confidence_score=40.0, consensus_ratio=0.4)
    rejected_profiles = service.analyze([rejected], ensemble_profiles={"QQQ": bad})
    service.attach([rejected], rejected_profiles)
    assert rejected.allowed is False
    assert "ENSEMBLE_DECISION_REJECTED" in rejected.rejection_reasons
    print("All Phase 10 decision-integration assertions passed.")


if __name__ == "__main__":
    main()
