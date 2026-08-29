from trading_ai.research_workstation.analytics import (
    PayoffAnalysisEngine,
    StrategyLegProfile,
    payoff_analysis_payload,
)


def main() -> None:
    legs = (
        StrategyLegProfile(
            symbol="AAA",
            option_type="PUT",
            side="SHORT",
            strike=100.0,
            premium=3.0,
            delta=-0.35,
            gamma=0.04,
            theta=-0.08,
            vega=0.12,
            rho=-0.05,
        ),
        StrategyLegProfile(
            symbol="AAA",
            option_type="PUT",
            side="LONG",
            strike=95.0,
            premium=1.2,
            delta=-0.20,
            gamma=0.03,
            theta=-0.05,
            vega=0.08,
            rho=-0.03,
        ),
    )

    analysis = PayoffAnalysisEngine().analyze(
        strategy_name="BULL_PUT_SPREAD",
        underlying_price=100.0,
        legs=legs,
        minimum_price=80.0,
        maximum_price=120.0,
        steps=161,
    )

    assert analysis.strategy_name == "BULL_PUT_SPREAD"
    assert analysis.net_credit_debit == 180.0
    assert analysis.maximum_profit == 180.0
    assert analysis.maximum_loss == 320.0
    assert any(
        abs(point - 98.2) < 0.01
        for point in analysis.breakeven_points
    )
    assert analysis.return_on_risk == 0.5625
    assert analysis.greeks.leg_count == 2
    assert analysis.greeks.total_delta == 15.0
    assert analysis.greeks.total_theta == 3.0
    assert (
        analysis.risk_classification.assignment_risk
        == "MODERATE"
    )
    assert len(analysis.visualization_series) == 5
    assert (
        analysis.visualization_series[0].name
        == "price_to_profit_loss"
    )

    payload = payoff_analysis_payload(analysis)
    assert payload["strategy_name"] == "BULL_PUT_SPREAD"
    assert payload["maximum_loss"] == 320.0
    assert len(payload["payoff_points"]) == 161

    print(
        "All Milestone 34 Phase 2 Step 3 Greeks/payoff "
        "backend assertions passed."
    )


if __name__ == "__main__":
    main()
