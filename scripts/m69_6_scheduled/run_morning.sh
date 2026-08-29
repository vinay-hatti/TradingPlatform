#!/bin/bash
set -euo pipefail
export PROJECT_DIR="/Users/vinay.hatti/TradingPlatform"
export UV_BIN="/opt/homebrew/bin/uv"
export JOB_NAME="morning_full_ingestion"
export LOCK_NAME="m69_6_market_pipeline"
export LOG_FILE="/Users/vinay.hatti/TradingPlatform/logs/m69_6_morning_ingestion.log"
export ENV_FILE_PRIMARY="/Users/vinay.hatti/TradingPlatform/.env"
export ENV_FILE_FALLBACK="/Users/vinay.hatti/.config/tradingplatform/m69_6.env"
source "/Users/vinay.hatti/TradingPlatform/scripts/m69_6_scheduled/common.sh"
UNIVERSE_ARGS=(--universe-file data/universe/us_listed_equities_etfs.csv --index-universe-file data/universe/us_market_indices.csv --asset-classes EQUITY,ETF,INDEX --end "$(date +%F)")
UNDERLYING_ARGS=("${UNIVERSE_ARGS[@]}" --lookback-days 1460 --underlying-fetch-mode auto --underlying-incremental-sessions 5 --underlying-stale-threshold-days 10 --max-workers 4 --request-interval 15 --require-stock-intelligence --require-institutional-options --require-finalize)
OPTIONS_ARGS=("${UNIVERSE_ARGS[@]}" --options-minimum-dte 1 --options-maximum-dte 180 --options-minimum-open-interest 1 --options-minimum-volume 0 --options-maximum-strike-distance-pct 0.40 --polygon-requests-per-second 8 --polygon-network-workers 1 --options-batch-size 10000 --require-institutional-options --require-finalize)
run_cmd "${UV_BIN}" run python scripts/ingest_underlying_data.py "${UNDERLYING_ARGS[@]}"
run_cmd "${UV_BIN}" run python scripts/ingest_options_data.py "${OPTIONS_ARGS[@]}"
run_cmd "${UV_BIN}" run python scripts/run_intraday_active_universe_shadow.py intraday
run_cmd "${UV_BIN}" run python scripts/run_intraday_exclusion_progression_certification.py cycle
echo "[$(date)] END job=${JOB_NAME} status=READY" | tee -a "${LOG_FILE}"
