# Polygon Bulk OHLCV Optimization — 2026-07-29

This cumulative package retains Polygon-only market data and adds a fast equity/ETF ingestion path.

## Runtime changes

- Underlying pickle cache reads/writes are disabled by default.
- PostgreSQL `price_history` remains authoritative.
- Normal daily runs use Polygon grouped daily market summaries: one request per market date for the entire U.S. stock market, filtered to the canonical equity/ETF universe.
- Default incremental refresh covers the latest three weekday sessions.
- Auto mode detects symbols older than 10 calendar days and repairs only those symbols with ticker-specific historical requests.
- Forced historical rebuilds use grouped daily requests across the requested date range.
- Existing global pacing, 429 circuit breaker, worker-local clients, timeout classification, and PostgreSQL upserts remain included.

## New CLI controls

- `--underlying-fetch-mode auto|grouped|per-symbol` (default `auto`)
- `--underlying-incremental-sessions N` (default `3`)
- `--underlying-stale-threshold-days N` (default `10`)
- `--enable-underlying-cache` (opt-in; cache is otherwise disabled)

## Apply

```bash
./APPLY_POLYGON_BULK_OHLCV_OPTIMIZATION.sh /Users/vinay.hatti/TradingPlatform
```

## Recommended daily full-pipeline run

Do not use `--force-underlying-refresh` for a normal daily cycle.

```bash
uv run python scripts/run_market_ingestion.py \
  --continue-on-error \
  --data-scope all \
  --options-minimum-dte 1 \
  --options-maximum-dte 180 \
  --lookback-days 730 \
  --force-options-refresh \
  --force-dealer-refresh \
  --underlying-fetch-mode auto \
  --underlying-incremental-sessions 3 \
  --underlying-stale-threshold-days 10 \
  --request-interval 15
```

## Underlying-only fast refresh

```bash
uv run python scripts/run_market_ingestion.py \
  --continue-on-error \
  --data-scope underlying \
  --underlying-fetch-mode auto \
  --underlying-incremental-sessions 3 \
  --request-interval 15
```

## Full underlying rebuild

This is intentionally slower and should be used only for repair/backfill:

```bash
uv run python scripts/run_market_ingestion.py \
  --continue-on-error \
  --data-scope underlying \
  --lookback-days 730 \
  --force-underlying-refresh \
  --underlying-fetch-mode grouped \
  --request-interval 15
```
