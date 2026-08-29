#!/bin/bash
set -euo pipefail
export PROJECT_DIR="/Users/vinay.hatti/TradingPlatform"
export UV_BIN="/opt/homebrew/bin/uv"
export JOB_NAME="event_macro"
export LOCK_NAME="m69_6_market_pipeline"
export LOG_FILE="/Users/vinay.hatti/TradingPlatform/logs/m69_6_event_macro.log"
export ENV_FILE_PRIMARY="/Users/vinay.hatti/TradingPlatform/.env"
export ENV_FILE_FALLBACK="/Users/vinay.hatti/.config/tradingplatform/m69_6.env"
source "/Users/vinay.hatti/TradingPlatform/scripts/m69_6_scheduled/common.sh"
run_cmd "${UV_BIN}" run python scripts/sync_m69_event_calendar.py --horizon-months 6 --accept-governed-cache
DRY_RUN_JSON="$("${UV_BIN}" run python scripts/reconcile_m69_macro_event_integrity.py --start-year 2016)"
printf '%s\n' "${DRY_RUN_JSON}" | tee -a "${LOG_FILE}"
if DRY_RUN_JSON="${DRY_RUN_JSON}" "${UV_BIN}" run python - <<'PY'
import json, os, sys
x=json.loads(os.environ['DRY_RUN_JSON'])
completed=int(x.get('authoritative_completed_fomc_dates',0)); future=int(x.get('authoritative_future_fomc_dates',0)); bea=int(x.get('authoritative_bea_releases',0))
ok=70 <= completed <= 120 and future >= 1 and bea >= 250
print(f'guard completed_fomc={completed} future_fomc={future} bea={bea} pass={ok}')
sys.exit(0 if ok else 1)
PY
then
  run_cmd "${UV_BIN}" run python scripts/reconcile_m69_macro_event_integrity.py --start-year 2016 --apply
else
  echo "[$(date)] RECONCILIATION_SKIPPED safety guard failed" | tee -a "${LOG_FILE}"
fi
run_cmd "${UV_BIN}" run python scripts/realize_m69_event_outcomes.py
run_cmd "${UV_BIN}" run python scripts/compute_m69_event_expected_moves.py
run_cmd "${UV_BIN}" run python scripts/verify_m69_event_intelligence_hardening.py
echo "[$(date)] END job=${JOB_NAME} status=COMPLETED verification=PASSED" | tee -a "${LOG_FILE}"
