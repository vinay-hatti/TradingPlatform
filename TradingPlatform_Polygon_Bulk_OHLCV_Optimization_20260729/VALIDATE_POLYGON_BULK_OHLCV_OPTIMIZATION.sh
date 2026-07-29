#!/usr/bin/env bash
set -euo pipefail
TARGET="${1:-/Users/vinay.hatti/TradingPlatform}"
cd "$TARGET"
uv run python -m py_compile \
  src/trading_ai/market/service.py \
  src/trading_ai/market/downloader.py \
  src/trading_ai/market/providers/polygon.py \
  scripts/run_market_ingestion.py
uv run python scripts/run_market_ingestion.py \
  --continue-on-error \
  --data-scope underlying \
  --symbols AAPL,MSFT,SPY,QQQ \
  --lookback-days 30 \
  --underlying-fetch-mode grouped \
  --underlying-incremental-sessions 2 \
  --request-interval 15 \
  --max-retries 2 \
  --skip-trend-intelligence \
  --skip-market-overview \
  --skip-market-intelligence \
  --skip-publication
