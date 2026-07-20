from trading_ai.research_workstation.analysis import CandidateAnalysisEngine
from trading_ai.research_workstation.scanner.market_scanner_profile import (
    MarketCandidateProfile,
)


def main() -> None:
    candidate = MarketCandidateProfile(
        symbol="WEAK",
        price=12.0,
        average_volume=100_000,
        option_volume=20,
        open_interest=50,
        spread_pct=0.40,
        iv_rank=20.0,
        iv_percentile=25.0,
        atr_pct=6.0,
        trend_score=35.0,
        momentum_score=30.0,
        liquidity_score=25.0,
        volatility_score=35.0,
        regime_score=30.0,
        decision_confidence=25.0,
        expected_return=-0.05,
        risk_score=85.0,
        reward_risk_ratio=0.4,
        signal="PUT",
        regime="CHOP",
        metadata={},
    )

    analysis = CandidateAnalysisEngine().analyze(candidate)

    assert analysis.explanation.readiness == "NOT_READY"
    assert "Wide bid/ask spread" in (
        analysis.explanation.negative_contributors
    )
    assert "Institutional decision analytics unavailable" in (
        analysis.explanation.negative_contributors
    )
    assert analysis.risk.risk_grade == "HIGH"
    assert analysis.warnings

    print(
        "Milestone 34 Phase 2 Step 1 warning-generation "
        "assertions passed."
    )


if __name__ == "__main__":
    main()
