from trading_ai.research_workstation.analysis import (
    CandidateAnalysisEngine,
)
from trading_ai.research_workstation.analytics import (
    PayoffAnalysisEngine,
    StrategyLegProfile,
)
from trading_ai.research_workstation.explainability import (
    InstitutionalExplainabilityEngine,
    ScenarioDefinitionProfile,
)
from trading_ai.research_workstation.scanner.market_scanner_profile import (
    MarketCandidateProfile,
)


def main() -> None:
    candidate = CandidateAnalysisEngine().analyze(
        MarketCandidateProfile(
            symbol="RISK",
            price=100.0,
            average_volume=1_500_000,
            option_volume=1500,
            open_interest=7000,
            spread_pct=0.10,
            iv_rank=55.0,
            iv_percentile=60.0,
            atr_pct=3.0,
            trend_score=60.0,
            momentum_score=58.0,
            liquidity_score=70.0,
            volatility_score=65.0,
            regime_score=62.0,
            decision_confidence=60.0,
            expected_return=0.10,
            risk_score=55.0,
            reward_risk_ratio=1.2,
            signal="CALL",
            regime="TREND_UP",
            metadata={
                "institutional_decision": {
                    "available": True,
                    "allowed": True,
                    "selected": False,
                    "strategy": "SHORT_CALL",
                    "institutional_score": 55.0,
                    "calibrated_probability": 0.58,
                    "tail_risk_grade": "C",
                }
            },
        )
    )
    payoff = PayoffAnalysisEngine().analyze(
        strategy_name="SHORT_CALL",
        underlying_price=100.0,
        legs=(
            StrategyLegProfile(
                symbol="RISK",
                option_type="CALL",
                side="SHORT",
                strike=105.0,
                premium=2.0,
                delta=0.35,
                gamma=0.04,
                theta=-0.05,
                vega=0.12,
            ),
        ),
        minimum_price=50.0,
        maximum_price=180.0,
        steps=261,
    )
    scenarios = (
        ScenarioDefinitionProfile(
            name="BASE",
            description="Base",
            probability_weight=0.4,
        ),
        ScenarioDefinitionProfile(
            name="EXTREME_UP",
            description="Extreme upside move",
            price_shock_pct=0.60,
            volatility_shock_points=20.0,
            probability_weight=0.6,
        ),
    )

    profile = InstitutionalExplainabilityEngine().analyze(
        candidate=candidate,
        payoff=payoff,
        scenarios=scenarios,
    )

    comparison = profile.scenario_analysis.comparison
    assert comparison.worst_scenario == "EXTREME_UP"
    assert comparison.worst_projected_profit_loss < 0
    assert comparison.adverse_scenario_count >= 1
    assert "Payoff Efficiency" in profile.primary_risks
    assert profile.approval_status in {"WATCH", "REJECTED"}

    print(
        "Milestone 34 Phase 2 Step 4 scenario-stress "
        "assertions passed."
    )


if __name__ == "__main__":
    main()
