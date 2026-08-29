from __future__ import annotations

from trading_ai.research_workstation.analysis import (
    CandidateAnalysisEngine,
    CandidateAnalysisService,
    candidate_analysis_payload,
)
from trading_ai.research_workstation.scanner.market_scanner_profile import (
    MarketCandidateProfile,
)


def candidate() -> MarketCandidateProfile:
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
                "stop_loss_pct": -25.0,
                "take_profit_pct": 60.0,
                "rejection_reasons": [],
            }
        },
    )


def main() -> None:
    engine = CandidateAnalysisEngine()
    analysis = engine.analyze(candidate(), composite_score=91.5)

    assert analysis.symbol == "AAA", analysis
    assert analysis.composite_score == 91.5, analysis
    assert analysis.technical.technical_score > 80.0, analysis.technical
    assert analysis.liquidity.market_quality == "INSTITUTIONAL"
    assert analysis.volatility.volatility_state == "NORMAL"
    assert analysis.institutional.strategy == "BULL_PUT_SPREAD"
    assert analysis.institutional.calibrated_probability == 0.81
    assert analysis.risk.risk_grade == "LOW"
    assert analysis.explanation.readiness == "READY"
    assert analysis.trade_readiness_score > 75.0
    assert "Strong option volume" in (
        analysis.explanation.positive_contributors
    )

    payload = candidate_analysis_payload(analysis)
    assert payload["symbol"] == "AAA"
    assert payload["institutional"]["tail_risk_grade"] == "A"
    assert payload["explanation"]["recommendation"] == "BULL_PUT_SPREAD"

    service = CandidateAnalysisService(engine=engine)
    enriched = service.enrich_candidate(
        candidate(),
        composite_score=91.5,
    )
    assert "candidate_analysis" in enriched.metadata

    print(
        "All Milestone 34 Phase 2 Step 1 candidate-analysis "
        "assertions passed."
    )


if __name__ == "__main__":
    main()
