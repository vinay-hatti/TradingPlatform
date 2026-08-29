from types import SimpleNamespace

from trading_ai.research_workstation.scenario_comparison import (
    ScenarioComparisonEngine,
    scenario_comparison_payload,
)


def scenario(
    scenario_id,
    name,
    scenario_type,
    probability,
    expected_return,
    volatility,
    drawdown,
):
    return SimpleNamespace(
        scenario_id=scenario_id,
        name=name,
        scenario_type=scenario_type,
        probability=probability,
        expected_return_pct=expected_return,
        expected_volatility_pct=volatility,
        expected_drawdown_pct=drawdown,
    )


def main() -> None:
    research_case = SimpleNamespace(
        case_id="CASE-001",
        symbol="AAPL",
        strategy_name="BULL_PUT_SPREAD",
        confidence_score=0.85,
        scenarios=(
            scenario(
                "BASE", "Base Case", "BASE",
                0.50, 0.10, 0.24, 0.05
            ),
            scenario(
                "BULL", "Bull Case", "BULL",
                0.25, 0.22, 0.28, 0.03
            ),
            scenario(
                "BEAR", "Bear Case", "BEAR",
                0.25, -0.12, 0.36, 0.18
            ),
        ),
    )

    result = ScenarioComparisonEngine().compare(
        research_case=research_case,
        sensitivity_inputs={
            "implied_volatility": {
                "baseline": 0.24,
                "stressed": 0.25,
            },
            "underlying_price": {
                "baseline": 200.0,
                "stressed": 210.0,
            },
        },
    )

    assert result.status == "READY"
    assert result.probability_total == 1.0
    assert result.best_scenario_id == "BULL"
    assert result.worst_scenario_id == "BEAR"
    assert len(result.rankings) == 3
    assert len(result.scenario_deltas) == 3
    assert len(result.sensitivities) == 2
    assert result.weighted_expected_return_pct == 0.075
    assert result.recommendation.action in {
        "STRONG_BUY",
        "BUY",
        "OPPORTUNISTIC_BUY",
        "MONITOR",
    }
    assert result.comparison_grade in {"A", "B", "C", "D", "F"}
    assert result.comparison_score > 0.0

    payload = scenario_comparison_payload(result)
    assert payload["case_id"] == "CASE-001"
    assert payload["rankings"][0]["scenario_id"] == "BULL"

    print(
        "All Milestone 34 Phase 4 Step 2 scenario-comparison "
        "assertions passed."
    )


if __name__ == "__main__":
    main()
