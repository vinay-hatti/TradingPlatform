from pathlib import Path

root = Path(__file__).resolve().parents[1]
pages = (root / "ui/workstation/src/pages.tsx").read_text()
styles = (root / "ui/workstation/src/styles.css").read_text()

required = [
    "type OptionScannerStrategy =",
    "OPTION_SCANNER_STRATEGIES",
    "trend_following",
    "pullback",
    "breakout",
    "reversal",
    "momentum",
    "gamma_squeeze",
    "dealer_flow",
    "income",
    "OPTION_SCANNER_RISK_PROFILES",
    "applyStrategy",
    "minimumOpenInterest",
    "minimumOptionVolume",
    "maximumSpreadPct",
    "refresh_mode:persistedOnly?'cache_only':refreshMode",
    "auto_refresh:persistedOnly?false:autoRefresh",
    "Strategy intent",
    "Applied configuration",
]
for token in required:
    assert token in pages, f"Missing Phase 4 contract token: {token}"

assert "maximum_option_spread_pct:maximumSpreadPct" in pages
assert "minimum_option_open_interest:minimumOpenInterest" in pages
assert "minimum_option_volume:minimumOptionVolume" in pages
assert "risk_per_trade_pct:OPTION_SCANNER_RISK_PROFILES[riskProfile].riskPerTradePct" in pages
assert "strategy-card-grid" in styles
assert "strategy-card.active" in styles
assert "strategy-profile-row" in styles
assert "Run market ingestion" in pages, "Daily Scanner ingestion controls must remain intact"

print("Milestone 53 Phase 4 Option Scanner strategy-engine assertions passed.")
