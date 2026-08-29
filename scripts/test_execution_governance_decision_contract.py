import inspect
from pathlib import Path


def main():
    root = Path(__file__).resolve().parents[1]
    decision_text = (root / "src/trading_ai/strategy_engine/institutional_decision.py").read_text()
    result_text = (root / "src/trading_ai/strategy_engine/decision_run_result.py").read_text()
    engine_text = (root / "src/trading_ai/strategy_engine/institutional_decision_engine.py").read_text()
    for field in (
        "execution_governance_score", "execution_governance_allowed",
        "execution_champion_route_version", "execution_route_promotion_recommended",
    ): assert field in decision_text
    for field in (
        "execution_governance_integration_profile", "execution_route_registry_profile",
        "execution_champion_challenger_profile",
    ): assert field in result_text
    assert "ExecutionGovernanceIntegrationService" in engine_text
    assert "execution_governance_integration_profile=" in engine_text
    print("All execution governance decision-contract assertions passed.")


if __name__ == "__main__": main()
