# Milestone 46 Installation

```bash
cd /Users/vinay.hatti/TradingPlatform
tar -xzf ~/Downloads/TradingPlatform_Milestone46_MarketIntelligence_20260725.tar.gz --strip-components=1
uv run alembic upgrade head
uv run python scripts/run_m46_market_intelligence.py
```

Rebuild the workstation:

```bash
cd ui/workstation
npm install
npm run typecheck
npm run build
```

Validation:

```bash
cd /Users/vinay.hatti/TradingPlatform
uv run python scripts/test_m46_market_intelligence.py
uv run python scripts/test_m46_integration_contracts.py
uv run python scripts/test_m45_market_overview_contracts.py
uv run python scripts/test_m45_market_overview_ui.py
uv run python scripts/test_m44_daily_scanner_integration.py
```

Normal ingestion now refreshes Milestone 46 after Milestone 45. Use `--skip-market-intelligence` only for troubleshooting.
