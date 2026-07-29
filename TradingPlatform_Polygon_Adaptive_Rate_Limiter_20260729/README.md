# Polygon Adaptive Global Rate Limiter

This cumulative package supersedes the prior Polygon transport stabilization package.

## Root cause confirmed

The detailed errors show genuine HTTP 429 responses. A one-second global interval is still too fast for the REST allowance enforced on the configured Polygon account. The prior implementation also allowed other workers to continue until each independently encountered a 429.

## Changes

- Default Polygon equity/ETF interval changed from 1 second to 15 seconds.
- A 429 from any worker opens one process-wide cooldown circuit breaker.
- Every worker waits behind the same cooldown.
- After the first 429, the effective interval is at least 15 seconds.
- Repeated 429s increase the effective interval to 30, 60, and then higher as needed.
- The slower interval remains active for the rest of that ingestion run.
- Connection/timeout retry handling from the prior package remains intact.

## Apply

```bash
tar -xzf TradingPlatform_Polygon_Adaptive_Rate_Limiter_20260729.tar.gz
cd TradingPlatform_Polygon_Adaptive_Rate_Limiter_20260729
./APPLY_POLYGON_ADAPTIVE_RATE_LIMITER.sh /Users/vinay.hatti/TradingPlatform
```

## Controlled validation

```bash
./VALIDATE_POLYGON_ADAPTIVE_RATE_LIMITER.sh /Users/vinay.hatti/TradingPlatform
```

## Recommended full run

Do not force two years of underlying history during a normal daily cycle. The database already contains those rows. Use incremental underlying ingestion and refresh options as needed:

```bash
uv run python scripts/run_market_ingestion.py \
  --continue-on-error \
  --data-scope all \
  --options-minimum-dte 1 \
  --options-maximum-dte 180 \
  --lookback-days 730 \
  --force-options-refresh \
  --force-dealer-refresh \
  --max-workers 4 \
  --request-interval 15 \
  --polygon-rate-limit-floor 15 \
  --polygon-connect-timeout 5 \
  --polygon-read-timeout 30 \
  --polygon-sdk-retries 0 \
  --polygon-pools-per-worker 1 \
  --network-backoff 5 \
  --max-retries 5 \
  --initial-backoff 30 \
  --max-backoff 300
```

For a one-time full underlying rebuild, add `--force-underlying-refresh`.
