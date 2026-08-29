from trading_ai.research_workstation.analytics import (
    PayoffAnalysisEngine,
    StrategyLegProfile,
)


def main() -> None:
    long_call = PayoffAnalysisEngine().analyze(
        strategy_name="LONG_CALL",
        underlying_price=100.0,
        legs=(
            StrategyLegProfile(
                symbol="AAA",
                option_type="CALL",
                side="LONG",
                strike=100.0,
                premium=5.0,
                delta=0.50,
                gamma=0.04,
                theta=-0.08,
                vega=0.15,
                rho=0.05,
            ),
        ),
        minimum_price=50.0,
        maximum_price=200.0,
        steps=301,
    )

    assert long_call.maximum_profit is None
    assert long_call.maximum_loss == 500.0
    assert any(
        abs(point - 105.0) < 0.01
        for point in long_call.breakeven_points
    )
    assert "Maximum profit is theoretically unbounded" in (
        long_call.warnings
    )
    assert (
        long_call.risk_classification.assignment_risk
        == "LOW"
    )

    naked_short_call = PayoffAnalysisEngine().analyze(
        strategy_name="SHORT_CALL",
        underlying_price=100.0,
        legs=(
            StrategyLegProfile(
                symbol="AAA",
                option_type="CALL",
                side="SHORT",
                strike=110.0,
                premium=2.0,
            ),
        ),
        minimum_price=50.0,
        maximum_price=200.0,
        steps=301,
    )

    assert naked_short_call.maximum_profit == 200.0
    assert naked_short_call.maximum_loss is None
    assert (
        naked_short_call.risk_classification.assignment_risk
        == "HIGH"
    )
    assert "Maximum loss is theoretically unbounded" in (
        naked_short_call.warnings
    )

    print(
        "Milestone 34 Phase 2 Step 3 strategy edge-case "
        "assertions passed."
    )


if __name__ == "__main__":
    main()
