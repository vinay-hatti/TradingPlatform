#!/usr/bin/env bash
set -euo pipefail
cd "${1:-$(pwd)}"

uv run python scripts/run_market_ingestion.py \
  --continue-on-error \
  --data-scope underlying \
  --symbols AAPL,MSFT,SPY,QQQ \
  --lookback-days 30 \
  --force-underlying-refresh \
  --skip-dealer-positioning \
  --skip-trend-intelligence \
  --skip-market-overview \
  --skip-market-intelligence \
  --skip-publication \
  --max-workers 4 \
  --request-interval 1.0 \
  --polygon-connect-timeout 5 \
  --polygon-read-timeout 30 \
  --polygon-sdk-retries 0 \
  --polygon-pools-per-worker 1 \
  --network-backoff 5 \
  --max-retries 3

echo
echo "Run package tests with:"
echo "uv run pytest -q <package-dir>/tests/test_polygon_market_data_fix.py <package-dir>/tests/test_polygon_adaptive_rate_limiter.py"
