from trading_ai.research_workstation.analysis import (
    CandidateAnalysisEngine,
)
from trading_ai.research_workstation.analytics import (
    PayoffAnalysisEngine,
    StrategyLegProfile,
)
from trading_ai.research_workstation.explainability import (
    InstitutionalExplainabilityEngine,
    institutional_explainability_payload,
)
from trading_ai.research_workstation.scanner.market_scanner_profile import (
    MarketCandidateProfile,
)


def market_candidate() -> MarketCandidateProfile:
    return MarketCandidateProfile(
        symbol="AAA",
        price=100.0,
        average_volume=2_000_000,
        option_volume=5_000,
        open_interest=20_000,
        spread_pct=0.05,
        iv_rank=70.0,
        iv_percentile=75.0,
        atr_pct=2.0,
        trend_score=82.0,
        momentum_score=78.0,
        liquidity_score=90.0,
        volatility_score=80.0,
        regime_score=85.0,
        decision_confidence=92.0,
        expected_return=0.22,
        risk_score=18.0,
        reward_risk_ratio=2.0,
        signal="CALL",
        regime="TREND_UP",
        metadata={
            "institutional_decision": {
                "available": True,
                "allowed": True,
                "selected": True,
                "action": "ENTER",
                "readiness": "READY",
                "strategy": "BULL_PUT_SPREAD",
                "probability_of_profit": 0.78,
                "calibrated_probability": 0.81,
                "institutional_score": 88.0,
                "tail_risk_grade": "A",
                "recommended_position_size_pct": 2.5,
            }
        },
    )


def main() -> None:
    candidate = CandidateAnalysisEngine().analyze(
        market_candidate(),
        composite_score=91.5,
    )
    payoff = PayoffAnalysisEngine().analyze(
        strategy_name="BULL_PUT_SPREAD",
        underlying_price=100.0,
        legs=(
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
            ),
        ),
        minimum_price=80.0,
        maximum_price=120.0,
        steps=161,
    )

    profile = InstitutionalExplainabilityEngine().analyze(
        candidate=candidate,
        payoff=payoff,
    )

    assert profile.symbol == "AAA"
    assert profile.strategy == "BULL_PUT_SPREAD"
    assert profile.approval_status == "APPROVED", profile
    assert profile.explainability_score > 70.0
    assert len(profile.factor_contributions) == 6
    assert profile.primary_drivers
    assert len(profile.scenario_analysis.outcomes) == 6
    assert (
        profile.scenario_analysis.comparison.best_scenario
        in {item.name for item in profile.scenario_analysis.outcomes}
    )
    assert (
        profile.scenario_analysis.comparison.worst_scenario
        in {item.name for item in profile.scenario_analysis.outcomes}
    )
    assert profile.audit_narrative

    payload = institutional_explainability_payload(profile)
    assert payload["symbol"] == "AAA"
    assert payload["approval_status"] == "APPROVED"
    assert len(payload["factor_contributions"]) == 6
    assert len(payload["scenario_analysis"]["outcomes"]) == 6

    print(
        "All Milestone 34 Phase 2 Step 4 institutional "
        "explainability assertions passed."
    )


if __name__ == "__main__":
    main()
