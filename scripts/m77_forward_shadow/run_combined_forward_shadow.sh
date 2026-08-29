#!/bin/bash
set -uo pipefail

PROJECT_DIR="/Users/vinay.hatti/TradingPlatform"
UV_BIN="/opt/homebrew/bin/uv"
LOG_DIR="${PROJECT_DIR}/logs/m77_forward_shadow"
LOG_FILE="${LOG_DIR}/combined_forward_shadow.log"
M69_LOCK="${PROJECT_DIR}/reports/m69_event_intelligence/m69_6_market_pipeline.lock"
M77_LOCK="${PROJECT_DIR}/reports/m77/m77_forward_shadow_orchestrator.lock"
WAIT_SECONDS="${M77_FORWARD_SHADOW_WAIT_SECONDS:-7200}"
POLL_SECONDS="${M77_FORWARD_SHADOW_POLL_SECONDS:-60}"

mkdir -p "${LOG_DIR}" "${PROJECT_DIR}/reports/m77"
cd "${PROJECT_DIR}"

log() { echo "[$(date)] $*" | tee -a "${LOG_FILE}"; }

cleanup() { rm -rf "${M77_LOCK}" 2>/dev/null || true; }
trap cleanup EXIT INT TERM

if ! mkdir "${M77_LOCK}" 2>/dev/null; then
  pid=""
  [[ -f "${M77_LOCK}/owner" ]] && pid="$(awk -F= '$1=="pid"{print $2}' "${M77_LOCK}/owner" 2>/dev/null || true)"
  if [[ -n "${pid}" ]] && kill -0 "${pid}" 2>/dev/null; then
    log "SKIPPED_DUPLICATE_ORCHESTRATOR active_pid=${pid}"
    exit 0
  fi
  rm -rf "${M77_LOCK}"
  mkdir "${M77_LOCK}"
fi

{
  echo "pid=$$"
  echo "started_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
} > "${M77_LOCK}/owner"

waited=0
while [[ -d "${M69_LOCK}" ]]; do
  owner_pid=""
  [[ -f "${M69_LOCK}/owner" ]] && owner_pid="$(awk -F= '$1=="pid"{print $2}' "${M69_LOCK}/owner" 2>/dev/null || true)"
  if [[ -n "${owner_pid}" ]] && kill -0 "${owner_pid}" 2>/dev/null; then
    if (( waited >= WAIT_SECONDS )); then
      log "DEFERRED_PRODUCTION_PIPELINE_STILL_ACTIVE active_pid=${owner_pid} waited_seconds=${waited}"
      exit 0
    fi
    log "WAITING_FOR_PRODUCTION_PIPELINE active_pid=${owner_pid} waited_seconds=${waited}"
    sleep "${POLL_SECONDS}"
    waited=$((waited + POLL_SECONDS))
    continue
  fi
  log "RECOVERING_STALE_M69_LOCK"
  rm -rf "${M69_LOCK}" 2>/dev/null || true
done

log "START combined M77 forward-shadow orchestration"

declare -a failures=()

run_step() {
  local label="$1"
  shift
  log "RUN ${label}"
  "$@" >> "${LOG_FILE}" 2>&1
  local rc=$?
  if (( rc != 0 )); then
    failures+=("${label}:rc=${rc}")
    log "DEGRADED ${label} rc=${rc} production_effect=NONE"
  fi
  return 0
}

if [[ -x "${PROJECT_DIR}/scripts/m77_6_shadow/run_daily_shadow_collector.sh" ]]; then
  run_step "M77.6 existing live-forward shadow collector" \
    /bin/bash "${PROJECT_DIR}/scripts/m77_6_shadow/run_daily_shadow_collector.sh"
else
  failures+=("M77.6:missing")
  log "DEGRADED M77.6 collector missing production_effect=NONE"
fi

run_step "M77.13 certified-baseline forward shadow" \
  "${UV_BIN}" run python scripts/run_m77_13_forward_shadow.py cycle \
  --confirm RUN_M77_13_FORWARD_SHADOW_CYCLE

run_step "M77.24.1 PSVE record" \
  "${UV_BIN}" run python scripts/run_m77_24_1_positive_selection_shadow.py \
  --project-root "${PROJECT_DIR}" --action record
run_step "M77.24.1 PSVE update" \
  "${UV_BIN}" run python scripts/run_m77_24_1_positive_selection_shadow.py \
  --project-root "${PROJECT_DIR}" --action update

run_step "M77.26.2 MGE record" \
  "${UV_BIN}" run python scripts/run_m77_26_2_management_geometry_shadow.py \
  --project-root "${PROJECT_DIR}" --action record
run_step "M77.26.2 MGE update" \
  "${UV_BIN}" run python scripts/run_m77_26_2_management_geometry_shadow.py \
  --project-root "${PROJECT_DIR}" --action update

run_step "M77.27.1 CQMI record" \
  "${UV_BIN}" run python scripts/run_m77_27_1_candidate_quality_management_interaction_shadow.py \
  --project-root "${PROJECT_DIR}" --action record
run_step "M77.27.1 CQMI update" \
  "${UV_BIN}" run python scripts/run_m77_27_1_candidate_quality_management_interaction_shadow.py \
  --project-root "${PROJECT_DIR}" --action update

run_step "M77.30 CPRE record" \
  "${UV_BIN}" run python scripts/run_m77_30_cross_sectional_capital_priority_shadow.py \
  --project-root "${PROJECT_DIR}" --action record
run_step "M77.30 CPRE update" \
  "${UV_BIN}" run python scripts/run_m77_30_cross_sectional_capital_priority_shadow.py \
  --project-root "${PROJECT_DIR}" --action update

run_step "M77.40 CACA record" \
  "${UV_BIN}" run python scripts/run_m77_40_capacity_aware_capital_allocation_shadow.py \
  --project-root "${PROJECT_DIR}" --action record
run_step "M77.40 CACA update" \
  "${UV_BIN}" run python scripts/run_m77_40_capacity_aware_capital_allocation_shadow.py \
  --project-root "${PROJECT_DIR}" --action update

if (( ${#failures[@]} > 0 )); then
  log "RESEARCH_DEGRADED failures=$(IFS=,; echo "${failures[*]}") production_effect=NONE"
  exit 1
fi

log "END combined M77 forward-shadow orchestration status=READY production_effect=NONE"
