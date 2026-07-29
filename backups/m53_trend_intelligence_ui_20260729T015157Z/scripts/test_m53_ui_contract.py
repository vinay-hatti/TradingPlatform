from pathlib import Path

def main() -> None:
    pages=Path("ui/workstation/src/pages.tsx").read_text()
    styles=Path("ui/workstation/src/styles.css").read_text()
    service=Path("src/trading_ai/market_overview/service.py").read_text()
    contracts=Path("src/trading_ai/market_overview/contracts.py").read_text()
    assert "TrendIntelligenceCandidateCard" in pages
    assert 'Card title="Trend Intelligence"' in pages
    assert 'Card title="Trend operational governance"' in pages
    assert "combined_trend_score_adjustment" in pages
    assert "reversal_risk_score" in pages
    assert "institutional_conviction_score" in pages
    assert ".trend-candidate-card" in styles
    assert ".trend-intelligence-grid" in styles
    assert "trend_intelligence_summary" in service
    assert '"trend_intelligence"' in service
    assert "trend_intelligence: dict[str, Any]" in contracts
    print("All Milestone 53 UI/API contract assertions passed.")

if __name__=="__main__":
    main()
