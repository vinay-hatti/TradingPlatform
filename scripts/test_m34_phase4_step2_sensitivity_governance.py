from types import SimpleNamespace

from trading_ai.research_workstation.scenario_comparison import (
    ScenarioComparisonEngine,
)


def main() -> None:
    research_case = SimpleNamespace(
        case_id="CASE-RISK",
        symbol="RISK",
        strategy_name="NAKED_SHORT_CALL",
        confidence_score=0.30,
        scenarios=(
            SimpleNamespace(
                scenario_id="ONLY",
                name="Only Case",
                scenario_type="BASE",
                probability=0.40,
                expected_return_pct=-0.10,
                expected_volatility_pct=0.50,
                expected_drawdown_pct=0.40,
            ),
        ),
    )

    result = ScenarioComparisonEngine().compare(
        research_case=research_case,
        sensitivity_inputs={
            "implied_volatility": {
                "baseline": 0.20,
                "stressed": 0.50,
            },
            "liquidity_score": {
                "baseline": 90.0,
                "stressed": 20.0,
            },
        },
    )

    assert result.status == "REJECTED"
    assert result.rejection_reasons
    assert result.warnings
    assert result.remediation_actions
    assert result.recommendation.action == "REJECT"
    assert any(
        item.classification == "CRITICAL"
        for item in result.sensitivities
    )
    assert result.probability_total == 0.4

    print(
        "Milestone 34 Phase 4 Step 2 sensitivity-governance "
        "assertions passed."
    )


if __name__ == "__main__":
    main()
