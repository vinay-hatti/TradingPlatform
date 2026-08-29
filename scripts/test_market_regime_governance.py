from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace

from trading_ai.strategy_engine.market_regime_drift_service import MarketRegimeDriftService
from trading_ai.strategy_engine.market_regime_governance_policy import MarketRegimeGovernancePolicy
from trading_ai.strategy_engine.market_regime_governance_service import MarketRegimeGovernanceService
from trading_ai.strategy_engine.market_regime_model_registry import MarketRegimeModelRegistry
from trading_ai.strategy_engine.market_regime_governance_serialization import market_regime_governance_to_dict


def profiles(regime, count, score=80.0, confidence=82.0, transition_every=10):
    return [SimpleNamespace(current_regime=regime if i % 5 else "TRANSITION", regime_score=score, confidence_score=confidence, transition_detected=(i % transition_every == 0)) for i in range(count)]


def main():
    reference = profiles("BULL_TREND", 80)
    recent = profiles("BULL_TREND", 30, score=78.0, confidence=80.0)
    drift = MarketRegimeDriftService().analyze(reference, recent)
    assert drift.valid is True
    assert 0.0 <= drift.drift_score <= 100.0

    champion = {"observation_count": 500, "detection_accuracy": 0.72, "forecast_accuracy": 0.68, "transition_f1": 0.61, "critical_false_positive_rate": 0.03, "model_score": 73.0}
    challenger = {"observation_count": 500, "detection_accuracy": 0.76, "forecast_accuracy": 0.71, "transition_f1": 0.64, "critical_false_positive_rate": 0.031, "model_score": 79.0}
    with TemporaryDirectory() as tmp:
        registry = MarketRegimeModelRegistry(Path(tmp) / "registry.json")
        registry.register("v1", {"trend_window": 60}, champion, activate=True)
        registry.register("v2", {"trend_window": 45}, challenger)
        policy = MarketRegimeGovernancePolicy(automatic_promotion_enabled=True)
        profile = MarketRegimeGovernanceService(policy=policy, registry=registry).evaluate(champion, challenger, drift, "v1", "v2")
        assert profile.valid is True
        assert profile.promotion_eligible is True
        assert profile.promotion_applied is True
        assert registry.active()["version"] == "v2"
        payload = market_regime_governance_to_dict(profile)
        assert payload["recommendation"] == "PROMOTE_CHALLENGER"
    print("All market-regime governance assertions passed.")


if __name__ == "__main__":
    main()
