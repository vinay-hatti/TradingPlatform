#!/bin/bash
set -euo pipefail
export PROJECT_DIR="/Users/vinay.hatti/TradingPlatform"
export UV_BIN="/opt/homebrew/bin/uv"
export JOB_NAME="futures_preopen_refresh"
export LOCK_NAME="m69_6_market_pipeline"
export LOG_FILE="/Users/vinay.hatti/TradingPlatform/logs/m71_futures_preopen.log"
export ENV_FILE_PRIMARY="/Users/vinay.hatti/TradingPlatform/.env"
export ENV_FILE_FALLBACK="/Users/vinay.hatti/.config/tradingplatform/m69_6.env"
source "/Users/vinay.hatti/TradingPlatform/scripts/m69_6_scheduled/common.sh"

[[ -f scripts/ingest_futures_data.py ]] || { echo "[$(date)] ERROR missing scripts/ingest_futures_data.py" | tee -a "${LOG_FILE}"; exit 1; }

run_cmd "/opt/homebrew/bin/uv" run python scripts/ingest_futures_data.py   --products ES,NQ,RTY   --lookback-days 3   --resolutions 1min,1session   --min-days-to-maturity 5

echo "[$(date)] END job=${JOB_NAME} status=READY" | tee -a "${LOG_FILE}"
