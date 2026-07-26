from pathlib import Path
root=Path(__file__).resolve().parents[1]
app=(root/'ui/workstation/src/App.tsx').read_text()
pages=(root/'ui/workstation/src/pages.tsx').read_text()
styles=(root/'ui/workstation/src/styles.css').read_text()
api=(root/'src/trading_ai/market_overview/router.py').read_text()
migration=(root/'migrations/versions/m45_001_market_overview.py').read_text()
for token in ['MarketOverviewPage','market: MarketOverviewPage']:
    assert token in app
for token in ['Market overview','Market health & breadth','Trend, momentum & regime','Sector performance & rotation','Dealer positioning & options structure','Volatility & options environment','Liquidity & participation','Cross-asset confirmation','Risk dashboard','Opportunity map','Data freshness']:
    assert token in pages, token
for token in ['market_overview_snapshot','market_breadth_snapshot','sector_rotation_snapshot','snapshot_timestamp']:
    assert token in migration
assert "'/latest'" in api and "'/refresh'" in api and "'/scanner-context'" in api
assert '.sector-heatmap' in styles and '.risk-alert-grid' in styles
print('Milestone 45 Market Overview UI and persistence assertions passed.')
