from dataclasses import fields
from pathlib import Path

from trading_ai.strategy_engine.decision_run_result import DecisionRunResult
from trading_ai.strategy_engine.institutional_decision import InstitutionalDecision
from trading_ai.strategy_engine.institutional_decision_engine import InstitutionalDecisionEngine


def main():
    decision_fields = {item.name for item in fields(InstitutionalDecision)}
    required = {
        "phase10_valid", "phase10_allowed", "adaptive_strategy_selected",
        "ensemble_selected_strategy", "ensemble_decision_score",
        "ensemble_meta_confidence", "dynamic_strategy_weight",
        "online_adaptation_score", "learning_state_version",
        "phase10_decision_integration_profile",
    }
    assert required <= decision_fields

    run_fields = {item.name for item in fields(DecisionRunResult)}
    assert {
        "adaptive_strategy_profiles", "strategy_learning_profiles",
        "dynamic_strategy_weighting_profile", "ensemble_decision_profiles",
        "online_adaptation_profile", "learning_state_registry_profile",
        "learning_state_promotion_profile", "phase10_decision_integration_profiles",
    } <= run_fields

    engine = InstitutionalDecisionEngine.__init__
    assert engine is not None
    source = Path(__file__).parents[1] / "src/trading_ai/strategy_engine/institutional_decision_engine.py"
    text = source.read_text()
    assert "Phase10DecisionIntegrationService" in text
    assert "phase10_decision_integration_profiles" in text
    print("All Phase 10 decision-contract assertions passed.")


if __name__ == "__main__":
    main()
