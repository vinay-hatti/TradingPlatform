from datetime import date

from trading_ai.scanner.cross_asset_intelligence.engine import (
    CrossAssetIntelligenceEngine,
)
from trading_ai.scanner.cross_asset_intelligence.reporting import (
    render_html_report,
)


def main():
    profile = CrossAssetIntelligenceEngine().evaluate(
        as_of_date=date(2026, 7, 20),
        intermarket_profile={
            "market_state": "RISK_ON",
            "confidence": 0.80,
            "governance_status": "READY",
        },
        sector_profile={
            "rotation_state": "BROAD_RISK_ON",
            "leadership_state": "OFFENSIVE",
            "confidence": 0.75,
            "leaders": ["XLK"],
            "laggards": ["XLU"],
            "governance_status": "READY",
        },
        correlation_profile={
            "correlation_regime": "LOW_CORRELATION",
            "dispersion_regime": "HIGH_DISPERSION",
            "market_structure_state": "SECURITY_SELECTION",
            "correlation_breakdown_ratio": 0.05,
            "confidence": 0.70,
            "governance_status": "READY",
        },
    )

    html = render_html_report(profile)

    assert "Cross-Asset &amp; Market Structure Intelligence" in html
    assert "Decision Integration and Phase Closure" in html
    assert "Decision Adjustment" in html
    assert "BULLISH" in html
    assert "SECURITY_SELECTION" in html

    print("Milestone 35 Phase 5 Step 5 reporting assertions passed.")


if __name__ == "__main__":
    main()
