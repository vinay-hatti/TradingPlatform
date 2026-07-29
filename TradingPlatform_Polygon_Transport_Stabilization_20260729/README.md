# TradingPlatform Polygon Transport Stabilization

Cumulative replacement based on the Polygon-only market-data package.

## Changes

- One reusable Polygon `RESTClient` per downloader worker thread.
- No shared urllib3 pool across worker threads.
- Polygon SDK retries default to `0`; the globally paced downloader controls retries.
- Explicit connect/read timeouts: 5s / 30s.
- Separate short network backoff (5s) and rate-limit backoff (minimum 60s).
- Full nested exception-chain reporting.
- Retry classification: `RATE_LIMIT`, `SERVER`, `CONNECTION`, `TIMEOUT`, `TRANSPORT`, `AUTH`, `PERMANENT`.
- Existing Polygon-only routing and PostgreSQL `price_history` upserts retained.

The official client uses urllib3 pools and supports constructor controls for connect timeout, read timeout, pool count, and retries. This package applies those controls per worker rather than sharing a single client across the executor.

## Apply

```bash
tar -xzf TradingPlatform_Polygon_Transport_Stabilization_20260729.tar.gz
cd TradingPlatform_Polygon_Transport_Stabilization_20260729

./APPLY_POLYGON_TRANSPORT_STABILIZATION.sh \
  /Users/vinay.hatti/TradingPlatform
```

## Controlled validation

```bash
./VALIDATE_POLYGON_TRANSPORT_STABILIZATION.sh \
  /Users/vinay.hatti/TradingPlatform
```

## Recommended full run

```bash
uv run python scripts/run_market_ingestion.py \
  --continue-on-error \
  --data-scope all \
  --options-minimum-dte 1 \
  --options-maximum-dte 180 \
  --lookback-days 730 \
  --force-underlying-refresh \
  --force-options-refresh \
  --force-dealer-refresh \
  --max-workers 4 \
  --request-interval 1.0 \
  --polygon-connect-timeout 5 \
  --polygon-read-timeout 30 \
  --polygon-sdk-retries 0 \
  --polygon-pools-per-worker 1 \
  --network-backoff 5 \
  --max-retries 5 \
  --initial-backoff 30 \
  --max-backoff 300
```

A real rate limit will now log `category=RATE_LIMIT` and wait at least 60 seconds. Connection and DNS failures will log their actual nested cause and initially wait about 5 seconds.
