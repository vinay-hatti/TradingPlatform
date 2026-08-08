#!/bin/bash
set -euo pipefail

PROJECT_DIR="${1:-/Users/vinay.hatti/TradingPlatform}"
USER_ID="$(id -u)"
LAUNCH_AGENTS_DIR="${HOME}/Library/LaunchAgents"
LOG_DIR="${PROJECT_DIR}/logs"
RUNNER_DIR="${PROJECT_DIR}/scripts/m69_6_scheduled"
ENV_FILE_PRIMARY="${PROJECT_DIR}/.env"
ENV_FILE_FALLBACK="${HOME}/.config/tradingplatform/m69_6.env"

FUTURES_LABEL="com.tradingplatform.m71-futures-preopen"
EVENT_LABEL="com.tradingplatform.m69-6-event-intelligence"
MORNING_LABEL="com.tradingplatform.m69-6-morning-ingestion"
INTRADAY_LABEL="com.tradingplatform.m69-6-intraday-options"
EOD_LABEL="com.tradingplatform.m69-6-end-of-day-ingestion"

fail() { echo "ERROR: $*" >&2; exit 1; }
[[ -d "${PROJECT_DIR}" ]] || fail "Project directory not found: ${PROJECT_DIR}"
[[ -f "${PROJECT_DIR}/scripts/sync_m69_event_calendar.py" ]] || fail "M69.6 scripts not found under ${PROJECT_DIR}"
[[ -f "${PROJECT_DIR}/scripts/ingest_futures_data.py" ]] || fail "M71 futures ingestion script not found: ${PROJECT_DIR}/scripts/ingest_futures_data.py"
mkdir -p "${LAUNCH_AGENTS_DIR}" "${LOG_DIR}" "${RUNNER_DIR}" "${HOME}/.config/tradingplatform"

resolve_uv() {
  local candidate
  for candidate in "${HOME}/.local/bin/uv" "/opt/homebrew/bin/uv" "/usr/local/bin/uv" "$(command -v uv 2>/dev/null || true)"; do
    if [[ -n "${candidate}" && -x "${candidate}" ]]; then printf '%s\n' "${candidate}"; return 0; fi
  done
  return 1
}
UV_BIN="$(resolve_uv)" || fail "Unable to locate executable uv"

cat > "${RUNNER_DIR}/common.sh" <<'COMMON'
#!/bin/bash
set -euo pipefail
PROJECT_DIR="${PROJECT_DIR:?}"
UV_BIN="${UV_BIN:?}"
JOB_NAME="${JOB_NAME:?}"
LOCK_NAME="${LOCK_NAME:-m69_6_market_pipeline}"
LOG_FILE="${LOG_FILE:?}"
ENV_FILE_PRIMARY="${ENV_FILE_PRIMARY:-${PROJECT_DIR}/.env}"
ENV_FILE_FALLBACK="${ENV_FILE_FALLBACK:-${HOME}/.config/tradingplatform/m69_6.env}"
mkdir -p "$(dirname "${LOG_FILE}")" "${PROJECT_DIR}/reports/m69_event_intelligence"
load_env_file() { local file="$1"; if [[ -f "${file}" ]]; then set -a; source "${file}"; set +a; fi; }
load_env_file "${ENV_FILE_PRIMARY}"
load_env_file "${ENV_FILE_FALLBACK}"
LOCK_DIR="${PROJECT_DIR}/reports/m69_event_intelligence/${LOCK_NAME}.lock"
LOCK_META="${LOCK_DIR}/owner"
cleanup_lock() { rm -rf "${LOCK_DIR}" 2>/dev/null || true; }
trap cleanup_lock EXIT INT TERM
if ! mkdir "${LOCK_DIR}" 2>/dev/null; then
  existing_pid=""
  [[ -f "${LOCK_META}" ]] && existing_pid="$(awk -F= '$1=="pid"{print $2}' "${LOCK_META}" 2>/dev/null || true)"
  if [[ -n "${existing_pid}" ]] && kill -0 "${existing_pid}" 2>/dev/null; then
    echo "[$(date)] SKIPPED_OVERLAP job=${JOB_NAME} active_pid=${existing_pid}" | tee -a "${LOG_FILE}"
    exit 0
  fi
  rm -rf "${LOCK_DIR}"
  mkdir "${LOCK_DIR}"
fi
{
  echo "pid=$$"
  echo "job=${JOB_NAME}"
  echo "started_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
} > "${LOCK_META}"
run_cmd() { echo "[$(date)] RUN: $*" | tee -a "${LOG_FILE}"; "$@" 2>&1 | tee -a "${LOG_FILE}"; }
cd "${PROJECT_DIR}"
echo "================================================================" | tee -a "${LOG_FILE}"
echo "[$(date)] START job=${JOB_NAME}" | tee -a "${LOG_FILE}"
COMMON
chmod 755 "${RUNNER_DIR}/common.sh"

# M71 futures pre-open refresh: captures the developing overnight ES/NQ/RTY
# session before Event/Macro Intelligence and the full morning ingestion.
cat > "${RUNNER_DIR}/run_futures_preopen.sh" <<EOF_FUTURES
#!/bin/bash
set -euo pipefail
export PROJECT_DIR="${PROJECT_DIR}"
export UV_BIN="${UV_BIN}"
export JOB_NAME="futures_preopen_refresh"
export LOCK_NAME="m69_6_market_pipeline"
export LOG_FILE="${LOG_DIR}/m71_futures_preopen.log"
export ENV_FILE_PRIMARY="${ENV_FILE_PRIMARY}"
export ENV_FILE_FALLBACK="${ENV_FILE_FALLBACK}"
source "${RUNNER_DIR}/common.sh"

[[ -f scripts/ingest_futures_data.py ]] || { echo "[\$(date)] ERROR missing scripts/ingest_futures_data.py" | tee -a "\${LOG_FILE}"; exit 1; }

run_cmd "${UV_BIN}" run python scripts/ingest_futures_data.py \
  --products ES,NQ,RTY \
  --lookback-days 3 \
  --resolutions 1min,1session \
  --min-days-to-maturity 5

echo "[\$(date)] END job=\${JOB_NAME} status=READY" | tee -a "\${LOG_FILE}"
EOF_FUTURES
chmod 755 "${RUNNER_DIR}/run_futures_preopen.sh"

cat > "${RUNNER_DIR}/run_event_macro.sh" <<EOF_EVENT
#!/bin/bash
set -euo pipefail
export PROJECT_DIR="${PROJECT_DIR}"
export UV_BIN="${UV_BIN}"
export JOB_NAME="event_macro"
export LOCK_NAME="m69_6_market_pipeline"
export LOG_FILE="${LOG_DIR}/m69_6_event_macro.log"
export ENV_FILE_PRIMARY="${ENV_FILE_PRIMARY}"
export ENV_FILE_FALLBACK="${ENV_FILE_FALLBACK}"
source "${RUNNER_DIR}/common.sh"
run_cmd "\${UV_BIN}" run python scripts/sync_m69_event_calendar.py --horizon-months 6
DRY_RUN_JSON="\$("\${UV_BIN}" run python scripts/reconcile_m69_macro_event_integrity.py --start-year 2016)"
printf '%s\n' "\${DRY_RUN_JSON}" | tee -a "\${LOG_FILE}"
if DRY_RUN_JSON="\${DRY_RUN_JSON}" "\${UV_BIN}" run python - <<'PY'
import json, os, sys
x=json.loads(os.environ['DRY_RUN_JSON'])
completed=int(x.get('authoritative_completed_fomc_dates',0)); future=int(x.get('authoritative_future_fomc_dates',0)); bea=int(x.get('authoritative_bea_releases',0))
ok=70 <= completed <= 120 and future >= 1 and bea >= 250
print(f'guard completed_fomc={completed} future_fomc={future} bea={bea} pass={ok}')
sys.exit(0 if ok else 1)
PY
then
  run_cmd "\${UV_BIN}" run python scripts/reconcile_m69_macro_event_integrity.py --start-year 2016 --apply
else
  echo "[\$(date)] RECONCILIATION_SKIPPED safety guard failed" | tee -a "\${LOG_FILE}"
fi
run_cmd "\${UV_BIN}" run python scripts/realize_m69_event_outcomes.py
run_cmd "\${UV_BIN}" run python scripts/compute_m69_event_expected_moves.py
run_cmd "\${UV_BIN}" run python scripts/verify_m69_event_intelligence_hardening.py
echo "[\$(date)] END job=\${JOB_NAME} status=READY" | tee -a "\${LOG_FILE}"
EOF_EVENT
chmod 755 "${RUNNER_DIR}/run_event_macro.sh"

write_ingestion_runner() {
  local mode target job_name log_file
  mode="$1"
  target="${RUNNER_DIR}/run_${mode}.sh"
  job_name=""
  log_file=""
  case "${mode}" in
    morning) job_name="morning_full_ingestion"; log_file="${LOG_DIR}/m69_6_morning_ingestion.log" ;;
    intraday) job_name="intraday_options_refresh"; log_file="${LOG_DIR}/m69_6_intraday_options.log" ;;
    eod) job_name="end_of_day_full_ingestion"; log_file="${LOG_DIR}/m69_6_end_of_day_ingestion.log" ;;
    *) fail "Unsupported ingestion runner mode: ${mode}" ;;
  esac
  cat > "${target}" <<EOF_RUN
#!/bin/bash
set -euo pipefail
export PROJECT_DIR="${PROJECT_DIR}"
export UV_BIN="${UV_BIN}"
export JOB_NAME="${job_name}"
export LOCK_NAME="m69_6_market_pipeline"
export LOG_FILE="${log_file}"
export ENV_FILE_PRIMARY="${ENV_FILE_PRIMARY}"
export ENV_FILE_FALLBACK="${ENV_FILE_FALLBACK}"
source "${RUNNER_DIR}/common.sh"
UNIVERSE_ARGS=(--universe-file data/universe/us_listed_equities_etfs.csv --index-universe-file data/universe/us_market_indices.csv --asset-classes EQUITY,ETF,INDEX --end "\$(date +%F)")
UNDERLYING_ARGS=("\${UNIVERSE_ARGS[@]}" --lookback-days 1460 --underlying-fetch-mode auto --underlying-incremental-sessions 5 --underlying-stale-threshold-days 10 --max-workers 4 --request-interval 15 --require-stock-intelligence --require-institutional-options --require-finalize)
OPTIONS_ARGS=("\${UNIVERSE_ARGS[@]}" --options-minimum-dte 1 --options-maximum-dte 180 --options-minimum-open-interest 1 --options-minimum-volume 0 --options-maximum-strike-distance-pct 0.40 --polygon-requests-per-second 8 --options-batch-size 10000 --require-institutional-options --require-finalize)
EOF_RUN
  case "${mode}" in
    morning)
      cat >> "${target}" <<'EOF_RUN'
run_cmd "${UV_BIN}" run python scripts/ingest_underlying_data.py "${UNDERLYING_ARGS[@]}"
run_cmd "${UV_BIN}" run python scripts/ingest_options_data.py "${OPTIONS_ARGS[@]}"
EOF_RUN
      ;;
    intraday)
      cat >> "${target}" <<'EOF_RUN'
run_cmd "${UV_BIN}" run python scripts/ingest_options_data.py "${OPTIONS_ARGS[@]}"
EOF_RUN
      ;;
    eod)
      cat >> "${target}" <<'EOF_RUN'
run_cmd "${UV_BIN}" run python scripts/ingest_underlying_data.py "${UNDERLYING_ARGS[@]}"
run_cmd "${UV_BIN}" run python scripts/ingest_options_data.py "${OPTIONS_ARGS[@]}" --force-options-refresh --force-dealer-refresh
EOF_RUN
      ;;
  esac
  cat >> "${target}" <<'EOF_RUN'
echo "[$(date)] END job=${JOB_NAME} status=READY" | tee -a "${LOG_FILE}"
EOF_RUN
  chmod 755 "${target}"
}
write_ingestion_runner morning
write_ingestion_runner intraday
write_ingestion_runner eod

write_plist() {
  local label runner calendar_xml plist
  label="$1"
  runner="$2"
  calendar_xml="$3"
  plist="${LAUNCH_AGENTS_DIR}/${label}.plist"
  cat > "${plist}" <<EOF_PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
<key>Label</key><string>${label}</string>
<key>ProgramArguments</key><array><string>/bin/bash</string><string>${runner}</string></array>
<key>WorkingDirectory</key><string>${PROJECT_DIR}</string>
<key>StartCalendarInterval</key>${calendar_xml}
<key>RunAtLoad</key><false/>
<key>ProcessType</key><string>Background</string>
<key>StandardOutPath</key><string>${LOG_DIR}/${label}.out.log</string>
<key>StandardErrorPath</key><string>${LOG_DIR}/${label}.err.log</string>
</dict></plist>
EOF_PLIST
  plutil -lint "${plist}" >/dev/null
}

write_plist "${FUTURES_LABEL}" "${RUNNER_DIR}/run_futures_preopen.sh" '<dict><key>Hour</key><integer>7</integer><key>Minute</key><integer>55</integer></dict>'
write_plist "${EVENT_LABEL}" "${RUNNER_DIR}/run_event_macro.sh" '<dict><key>Hour</key><integer>8</integer><key>Minute</key><integer>10</integer></dict>'
write_plist "${MORNING_LABEL}" "${RUNNER_DIR}/run_morning.sh" '<dict><key>Hour</key><integer>8</integer><key>Minute</key><integer>30</integer></dict>'
write_plist "${INTRADAY_LABEL}" "${RUNNER_DIR}/run_intraday.sh" '<array><dict><key>Hour</key><integer>9</integer><key>Minute</key><integer>30</integer></dict><dict><key>Hour</key><integer>10</integer><key>Minute</key><integer>30</integer></dict><dict><key>Hour</key><integer>11</integer><key>Minute</key><integer>30</integer></dict><dict><key>Hour</key><integer>12</integer><key>Minute</key><integer>30</integer></dict><dict><key>Hour</key><integer>13</integer><key>Minute</key><integer>30</integer></dict><dict><key>Hour</key><integer>14</integer><key>Minute</key><integer>30</integer></dict></array>'
write_plist "${EOD_LABEL}" "${RUNNER_DIR}/run_eod.sh" '<dict><key>Hour</key><integer>15</integer><key>Minute</key><integer>20</integer></dict>'

for label in "${FUTURES_LABEL}" "${EVENT_LABEL}" "${MORNING_LABEL}" "${INTRADAY_LABEL}" "${EOD_LABEL}"; do launchctl bootout "gui/${USER_ID}/${label}" 2>/dev/null || true; done
for label in "${FUTURES_LABEL}" "${EVENT_LABEL}" "${MORNING_LABEL}" "${INTRADAY_LABEL}" "${EOD_LABEL}"; do launchctl bootstrap "gui/${USER_ID}" "${LAUNCH_AGENTS_DIR}/${label}.plist"; launchctl enable "gui/${USER_ID}/${label}" 2>/dev/null || true; done

cat <<EOF_SUMMARY
Installed schedule (local Mac time):
07:55 ES/NQ/RTY futures pre-open refresh
08:10 Event and macro intelligence
08:30 Full morning underlying + options ingestion
09:30, 10:30, 11:30, 12:30, 13:30, 14:30 Options-only refresh
15:20 Full forced end-of-day underlying + options ingestion

All jobs share one overlap lock. If a prior job is still running, the next job exits with SKIPPED_OVERLAP.
Logs: ${LOG_DIR}
Runners: ${RUNNER_DIR}
EOF_SUMMARY
