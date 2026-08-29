from dataclasses import dataclass, field

from trading_ai.strategy_engine.ensemble_decision_engine import EnsembleDecisionEngine
from trading_ai.strategy_engine.ensemble_decision_integration import attach_ensemble_decision
from trading_ai.strategy_engine.ensemble_decision_serialization import ensemble_to_dict
from trading_ai.strategy_engine.ensemble_decision_service import EnsembleDecisionService


@dataclass
class Holder:
    metadata: dict = field(default_factory=dict)


def main():
    adaptive = {
        "IRON_CONDOR": {"strategy": "IRON_CONDOR", "adaptive_score": 82, "confidence_score": 86, "allowed": True, "direction": "NEUTRAL"},
        "LONG_CALL": {"strategy": "LONG_CALL", "adaptive_score": 67, "confidence_score": 65, "allowed": True, "direction": "BULLISH"},
    }
    learned = {
        "IRON_CONDOR": {"strategy": "IRON_CONDOR", "performance_score": 80, "confidence_score": 83, "allowed": True, "direction": "NEUTRAL"},
        "LONG_CALL": {"strategy": "LONG_CALL", "performance_score": 55, "confidence_score": 61, "allowed": False, "direction": "BULLISH"},
    }
    probability = {
        "IRON_CONDOR": {"strategy": "IRON_CONDOR", "probability_score": 78, "confidence_score": 80, "allowed": True, "direction": "NEUTRAL"},
        "LONG_CALL": {"strategy": "LONG_CALL", "probability_score": 62, "confidence_score": 60, "allowed": True, "direction": "BULLISH"},
    }
    regime = {
        "IRON_CONDOR": {"strategy": "IRON_CONDOR", "regime_score": 76, "confidence_score": 75, "allowed": True, "direction": "NEUTRAL"},
        "LONG_CALL": {"strategy": "LONG_CALL", "regime_score": 45, "confidence_score": 58, "allowed": False, "direction": "BEARISH"},
    }
    execution = {
        "IRON_CONDOR": {"strategy": "IRON_CONDOR", "execution_score": 84, "confidence_score": 79, "allowed": True, "direction": "NEUTRAL"},
        "LONG_CALL": {"strategy": "LONG_CALL", "execution_score": 59, "confidence_score": 55, "allowed": True, "direction": "BULLISH"},
    }
    service = EnsembleDecisionService()
    profile = service.decide("SPY", ["IRON_CONDOR", "LONG_CALL"], adaptive=adaptive, learned=learned, probability=probability, regime=regime, execution=execution)
    assert profile.valid and profile.allowed
    assert profile.selected_strategy == "IRON_CONDOR"
    assert profile.ensemble_score >= 75
    assert profile.meta_confidence_score >= 75
    assert profile.strategies[0].component_count == 5
    assert profile.strategies[0].consensus_ratio == 1.0
    long_call = next(item for item in profile.strategies if item.strategy == "LONG_CALL")
    assert not long_call.allowed
    assert "DIRECTION_CONFLICT" in long_call.rejection_reasons
    payload = ensemble_to_dict(profile)
    assert payload["selected_strategy"] == "IRON_CONDOR"
    holder = attach_ensemble_decision(Holder(), profile)
    assert holder.metadata["ensemble_decision_profile"] is profile
    target = attach_ensemble_decision({}, profile)
    assert target["ensemble_allowed"] is True
    sparse = EnsembleDecisionEngine().decide("QQQ", ["LONG_PUT"], adaptive={"LONG_PUT": {"strategy": "LONG_PUT", "adaptive_score": 70, "confidence_score": 70, "allowed": True}})
    assert not sparse.allowed
    assert "COMPONENT_COUNT_BELOW_POLICY" in sparse.rejection_reasons
    print("All ensemble-decision and meta-confidence assertions passed.")


if __name__ == "__main__":
    main()
