from pathlib import Path

root = Path(__file__).resolve().parents[1]

checks = {
    "migration": (
        "migrations/versions/m46_001_market_intelligence.py",
        [
            "sector_membership",
            "correlation_pair_snapshot",
            "market_sentiment_snapshot",
            "dealer_position_change_snapshot",
            "market_opportunity_snapshot",
        ],
    ),
    "api": (
        "src/trading_ai/market_intelligence/router.py",
        ["/correlation", "/sectors", "/dealer-migration", "/risk", "/opportunities"],
    ),
    "scanner_context": (
        "src/trading_ai/daily/scanner.py",
        ["published_state_context", "candidate_fields()"],
    ),
    "intelligence_adjustments": (
        "src/trading_ai/market_intelligence/integration.py",
        ["intelligence_adjustments", "sector_score_adjustment", "risk_score_adjustment"],
    ),
    "ui": (
        "ui/workstation/src/pages.tsx",
        [
            "correlation_regime",
            "sentiment_score",
            "data?.sectors",
            "dealer_positioning",
            "opportunity_map",
        ],
    ),
    "ingestion": (
        "scripts/run_market_ingestion.py",
        ["skip-market-intelligence", "MarketIntelligenceService"],
    ),
}

for name, (path, tokens) in checks.items():
    target = root / path
    assert target.exists(), (name, f"missing file: {path}")
    text = target.read_text()
    for token in tokens:
        assert token in text, (name, token)

print("Milestone 46 integration contract assertions passed.")
