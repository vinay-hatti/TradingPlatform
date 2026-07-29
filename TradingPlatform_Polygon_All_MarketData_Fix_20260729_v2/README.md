# Polygon-only market-data fix

This drop-in package changes TradingPlatform to use Polygon for:

- Equity and ETF daily OHLCV
- Index daily OHLCV
- Option chains and option quotes (existing Polygon path retained)

It also fixes the missing `price_history` persistence by performing atomic PostgreSQL upserts on `(symbol, date)`, adds inserted/updated/persisted counts, isolates Polygon cache files, and rejects multi-session stale cache coverage.

## Apply

```bash
tar -xzf TradingPlatform_Polygon_All_MarketData_Fix_20260729_v2.tar.gz
cd TradingPlatform_Polygon_All_MarketData_Fix_20260729_v2
./APPLY_POLYGON_ALL_MARKETDATA_FIX.sh /Users/vinay.hatti/TradingPlatform
```

## Controlled validation

```bash
./VALIDATE_POLYGON_ALL_MARKETDATA_FIX.sh /Users/vinay.hatti/TradingPlatform
```

## Full ingestion

```bash
cd /Users/vinay.hatti/TradingPlatform
uv run python scripts/run_market_ingestion.py \
  --data-scope all \
  --lookback-days 730 \
  --force-underlying-refresh \
  --force-options-refresh \
  --force-dealer-refresh \
  --max-workers 1 \
  --request-interval 1 \
  --continue-on-error
```
