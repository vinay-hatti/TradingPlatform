# Install and validate

```bash
cd /Users/vinay.hatti/TradingPlatform

tar -xzf ~/Downloads/TradingPlatform_Milestone48_IndexMarketOverview_20260725.tar.gz --strip-components=1
```

No database migration is required.

Validate:

```bash
uv run python scripts/test_authoritative_index_ingestion.py
uv run python scripts/test_m48_index_market_overview.py
uv run python -m py_compile src/trading_ai/market_overview/service.py
```

Refresh persisted market overview after SPX, NDX, and RUT ingestion:

```bash
uv run python scripts/run_m45_market_overview.py
```

Or use **Refresh analytics** on the Market Overview page.

Restart the API and UI processes if they are already running so the updated backend and React source are loaded.
