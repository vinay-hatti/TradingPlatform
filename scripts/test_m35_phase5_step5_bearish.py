from datetime import date

from trading_ai.scanner.cross_asset_intelligence.engine import (
    CrossAssetIntelligenceEngine,
)


def main():
    profile = CrossAssetIntelligenceEngine().evaluate(
        as_of_date=date(2026, 7, 20),
        intermarket_profile={
            "market_state": "RISK_OFF",
            "confidence": 0.90,
            "governance_status": "READY",
        },
        sector_profile={
            "rotation_state": "DEFENSIVE_ROTATION",
            "leadership_state": "DEFENSIVE",
            "confidence": 0.80,
            "leaders": ["XLU", "XLP", "XLV"],
            "laggards": ["XLK", "XLY", "XLI"],
            "governance_status": "READY",
        },
        correlation_profile={
            "correlation_regime": "HIGH_CORRELATION",
            "dispersion_regime": "LOW_DISPERSION",
            "market_structure_state": "MACRO_DOMINATED",
            "correlation_breakdown_ratio": 0.10,
            "confidence": 0.75,
            "governance_status": "READY",
        },
    )

    assert profile.macro_regime == "RISK_OFF"
    assert profile.tactical_bias == "BEARISH"
    assert profile.systemic_risk_level == "ELEVATED"
    assert profile.decision_adjustment.preferred_direction == "PUT"
    assert profile.decision_adjustment.put_score_adjustment > 0
    assert profile.decision_adjustment.call_score_adjustment < 0
    assert profile.decision_adjustment.position_size_multiplier == 0.75
    assert profile.decision_adjustment.confidence_multiplier == 0.85

    print("Milestone 35 Phase 5 Step 5 bearish assertions passed.")


if __name__ == "__main__":
    main()
