#!/bin/zsh
set -uo pipefail

PROJECT_ROOT="/Users/vinay.hatti/TradingPlatform"
M77_RUNNER="${PROJECT_ROOT}/scripts/m77_forward_shadow/run_combined_forward_shadow.sh"
M77_LOG="${PROJECT_ROOT}/logs/m77_forward_shadow/combined_forward_shadow.log"
M78_RUNNER="${PROJECT_ROOT}/scripts/run_m78_daily_shadow.py"
COMBINED_LOG_DIR="${PROJECT_ROOT}/logs/m77_m78_combined_shadow"
COMBINED_LOG="${COMBINED_LOG_DIR}/combined_daily_shadow.log"
LOCK_DIR="${PROJECT_ROOT}/reports/m78/m77_m78_combined_daily_shadow.lock"

mkdir -p "${COMBINED_LOG_DIR}" "${PROJECT_ROOT}/reports/m78"
cd "${PROJECT_ROOT}" || exit 20

log() {
  echo "[$(date)] $*" | tee -a "${COMBINED_LOG}"
}

cleanup() {
  rm -rf "${LOCK_DIR}" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

if ! mkdir "${LOCK_DIR}" 2>/dev/null; then
  owner_pid=""
  [[ -f "${LOCK_DIR}/owner" ]] && owner_pid="$(awk -F= '$1=="pid"{print $2}' "${LOCK_DIR}/owner" 2>/dev/null || true)"
  if [[ -n "${owner_pid}" ]] && kill -0 "${owner_pid}" 2>/dev/null; then
    log "SKIPPED_DUPLICATE_COMBINED_ORCHESTRATOR active_pid=${owner_pid}"
    exit 0
  fi
  log "RECOVERING_STALE_COMBINED_LOCK"
  rm -rf "${LOCK_DIR}" 2>/dev/null || true
  mkdir "${LOCK_DIR}" || exit 21
fi

{
  echo "pid=$$"
  echo "started_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
} > "${LOCK_DIR}/owner"

UV_BIN=""
for candidate in /opt/homebrew/bin/uv /usr/local/bin/uv "${HOME}/.local/bin/uv"; do
  if [[ -x "${candidate}" ]]; then
    UV_BIN="${candidate}"
    break
  fi
done
if [[ -z "${UV_BIN}" ]]; then
  UV_BIN="$(command -v uv 2>/dev/null || true)"
fi
if [[ -z "${UV_BIN}" || ! -x "${UV_BIN}" ]]; then
  log "FAILED UV_NOT_FOUND production_effect=NONE"
  exit 22
fi

if [[ ! -x "${M77_RUNNER}" ]]; then
  log "FAILED M77_RUNNER_MISSING path=${M77_RUNNER} production_effect=NONE"
  exit 23
fi
if [[ ! -f "${M78_RUNNER}" ]]; then
  log "FAILED M78_RUNNER_MISSING path=${M78_RUNNER} authority_effect=FALSE"
  exit 24
fi

log "START combined nightly research orchestration M77_then_M78 authority_effect=FALSE"

before_bytes=0
if [[ -f "${M77_LOG}" ]]; then
  before_bytes="$(wc -c < "${M77_LOG}" | tr -d ' ')"
fi

log "RUN M77 forward-shadow orchestrator"
/bin/bash "${M77_RUNNER}"
m77_rc=$?

if (( m77_rc != 0 )); then
  log "M77_FAILED rc=${m77_rc}; M78_SKIPPED fail_closed=TRUE production_effect=NONE"
  exit "${m77_rc}"
fi

m77_delta=""
if [[ -f "${M77_LOG}" ]]; then
  after_bytes="$(wc -c < "${M77_LOG}" | tr -d ' ')"
  if (( after_bytes >= before_bytes )); then
    start_byte=$((before_bytes + 1))
    m77_delta="$(tail -c +"${start_byte}" "${M77_LOG}" 2>/dev/null || true)"
  fi
fi

if ! printf '%s\n' "${m77_delta}" | grep -Fq \
  "END combined M77 forward-shadow orchestration status=READY production_effect=NONE"; then
  if printf '%s\n' "${m77_delta}" | grep -Fq "DEFERRED_PRODUCTION_PIPELINE_STILL_ACTIVE"; then
    reason="M77_DEFERRED_PRODUCTION_PIPELINE_ACTIVE"
  elif printf '%s\n' "${m77_delta}" | grep -Fq "SKIPPED_DUPLICATE_ORCHESTRATOR"; then
    reason="M77_SKIPPED_DUPLICATE"
  else
    reason="M77_READY_MARKER_NOT_OBSERVED"
  fi
  log "${reason}; M78_SKIPPED fail_closed=TRUE authority_effect=FALSE"
  exit 0
fi

log "M77_READY verified_explicit_completion_marker=TRUE"

log "RUN M78 daily shadow"
"${UV_BIN}" run python scripts/run_m78_daily_shadow.py >> "${COMBINED_LOG}" 2>&1
m78_rc=$?

if (( m78_rc != 0 )); then
  log "M78_FAILED rc=${m78_rc} M77_status=READY authority_effect=FALSE"
  exit "${m78_rc}"
fi

log "END combined nightly research orchestration status=READY M77=READY M78=READY authority_effect=FALSE"
exit 0
