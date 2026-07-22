from datetime import date

from trading_ai.scanner.cross_asset_intelligence.contracts import (
    CrossAssetIntelligenceGovernanceStatus,
)
from trading_ai.scanner.cross_asset_intelligence.engine import (
    CrossAssetIntelligenceEngine,
)


def main():
    intermarket = {
        "market_state": "RISK_ON",
        "confidence": 0.80,
        "governance_status": "READY",
        "correlation_breakdown_ratio": 0.0,
    }
    sector = {
        "rotation_state": "BROAD_RISK_ON",
        "leadership_state": "OFFENSIVE",
        "confidence": 0.75,
        "leaders": ["XLK", "XLY", "XLI"],
        "laggards": ["XLU", "XLP", "XLV"],
        "governance_status": "READY",
    }
    correlation = {
        "correlation_regime": "LOW_CORRELATION",
        "dispersion_regime": "HIGH_DISPERSION",
        "market_structure_state": "SECURITY_SELECTION",
        "correlation_breakdown_ratio": 0.05,
        "confidence": 0.70,
        "governance_status": "READY",
    }

    profile = CrossAssetIntelligenceEngine().evaluate(
        as_of_date=date(2026, 7, 20),
        intermarket_profile=intermarket,
        sector_profile=sector,
        correlation_profile=correlation,
    )

    assert (
        profile.governance_status
        == CrossAssetIntelligenceGovernanceStatus.READY
    )
    assert profile.macro_regime == "RISK_ON"
    assert profile.tactical_bias == "BULLISH"
    assert profile.opportunity_regime == "SECURITY_SELECTION"
    assert profile.systemic_risk_level == "NORMAL"
    assert profile.decision_adjustment.preferred_direction == "CALL"
    assert profile.decision_adjustment.call_score_adjustment > 0
    assert profile.decision_adjustment.put_score_adjustment < 0
    assert profile.decision_adjustment.allow_new_risk is True
    assert profile.decision_adjustment.position_size_multiplier == 1.0

    print("Milestone 35 Phase 5 Step 5 engine assertions passed.")


if __name__ == "__main__":
    main()
