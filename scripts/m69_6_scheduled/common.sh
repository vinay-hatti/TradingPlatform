#!/bin/bash
set -euo pipefail

PROJECT_DIR="${PROJECT_DIR:?}"
UV_BIN="${UV_BIN:?}"
JOB_NAME="${JOB_NAME:?}"
LOCK_NAME="${LOCK_NAME:-m69_6_market_pipeline}"
LOG_FILE="${LOG_FILE:?}"
ENV_FILE_PRIMARY="${ENV_FILE_PRIMARY:-${PROJECT_DIR}/.env}"
ENV_FILE_FALLBACK="${ENV_FILE_FALLBACK:-${HOME}/.config/tradingplatform/m69_6.env}"

# Governed lock policy:
# Critical ingestion jobs wait for the shared pipeline lock.
# Repeatable/noncritical jobs continue to skip immediately on overlap.
case "${JOB_NAME}" in
  morning_full_ingestion|end_of_day_ingestion)
    LOCK_POLICY="${LOCK_POLICY:-WAIT}"
    LOCK_WAIT_SECONDS="${LOCK_WAIT_SECONDS:-2700}"
    LOCK_POLL_SECONDS="${LOCK_POLL_SECONDS:-15}"
    ;;
  *)
    LOCK_POLICY="${LOCK_POLICY:-SKIP}"
    LOCK_WAIT_SECONDS="${LOCK_WAIT_SECONDS:-0}"
    LOCK_POLL_SECONDS="${LOCK_POLL_SECONDS:-15}"
    ;;
esac

mkdir -p "$(dirname "${LOG_FILE}")" "${PROJECT_DIR}/reports/m69_event_intelligence"

load_env_file() {
  local file="$1"
  if [[ -f "${file}" ]]; then
    set -a
    source "${file}"
    set +a
  fi
}
load_env_file "${ENV_FILE_PRIMARY}"
load_env_file "${ENV_FILE_FALLBACK}"

LOCK_DIR="${PROJECT_DIR}/reports/m69_event_intelligence/${LOCK_NAME}.lock"
LOCK_META="${LOCK_DIR}/owner"

read_lock_field() {
  local key="$1"
  [[ -f "${LOCK_META}" ]] || return 0
  awk -F= -v key="${key}" '$1==key{print substr($0,index($0,"=")+1)}' "${LOCK_META}" 2>/dev/null || true
}

cleanup_lock() {
  if [[ -f "${LOCK_META}" ]]; then
    local owner_pid=""
    owner_pid="$(read_lock_field pid)"
    if [[ "${owner_pid}" == "$$" ]]; then
      rm -rf "${LOCK_DIR}" 2>/dev/null || true
    fi
  fi
}
trap cleanup_lock EXIT INT TERM

try_acquire_lock() {
  if mkdir "${LOCK_DIR}" 2>/dev/null; then
    return 0
  fi

  local existing_pid=""
  existing_pid="$(read_lock_field pid)"

  # Recover only stale/unowned locks.
  if [[ -z "${existing_pid}" ]] || ! kill -0 "${existing_pid}" 2>/dev/null; then
    local stale_job=""
    stale_job="$(read_lock_field job)"
    echo "[$(date)] STALE_LOCK_RECOVERY job=${JOB_NAME} stale_pid=${existing_pid:-UNKNOWN} stale_job=${stale_job:-UNKNOWN}" | tee -a "${LOG_FILE}"
    rm -rf "${LOCK_DIR}"
    mkdir "${LOCK_DIR}"
    return 0
  fi

  return 1
}

if ! try_acquire_lock; then
  existing_pid="$(read_lock_field pid)"
  existing_job="$(read_lock_field job)"
  existing_started_at="$(read_lock_field started_at)"

  if [[ "${LOCK_POLICY}" == "SKIP" ]]; then
    echo "[$(date)] SKIPPED_OVERLAP job=${JOB_NAME} active_pid=${existing_pid:-UNKNOWN} active_job=${existing_job:-UNKNOWN} active_started_at=${existing_started_at:-UNKNOWN} lock_policy=SKIP" | tee -a "${LOG_FILE}"
    exit 0
  fi

  if [[ "${LOCK_POLICY}" != "WAIT" ]]; then
    echo "[$(date)] LOCK_POLICY_ERROR job=${JOB_NAME} policy=${LOCK_POLICY}" | tee -a "${LOG_FILE}"
    exit 64
  fi

  waited=0
  acquired=0
  echo "[$(date)] WAITING_FOR_LOCK job=${JOB_NAME} active_pid=${existing_pid:-UNKNOWN} active_job=${existing_job:-UNKNOWN} active_started_at=${existing_started_at:-UNKNOWN} timeout_seconds=${LOCK_WAIT_SECONDS} poll_seconds=${LOCK_POLL_SECONDS}" | tee -a "${LOG_FILE}"

  while (( waited < LOCK_WAIT_SECONDS )); do
    sleep "${LOCK_POLL_SECONDS}"
    waited=$((waited + LOCK_POLL_SECONDS))

    if try_acquire_lock; then
      acquired=1
      echo "[$(date)] LOCK_ACQUIRED_AFTER_WAIT job=${JOB_NAME} waited_seconds=${waited}" | tee -a "${LOG_FILE}"
      break
    fi

    if (( waited % 60 == 0 )); then
      existing_pid="$(read_lock_field pid)"
      existing_job="$(read_lock_field job)"
      echo "[$(date)] STILL_WAITING_FOR_LOCK job=${JOB_NAME} waited_seconds=${waited} active_pid=${existing_pid:-UNKNOWN} active_job=${existing_job:-UNKNOWN}" | tee -a "${LOG_FILE}"
    fi
  done

  if (( acquired == 0 )); then
    existing_pid="$(read_lock_field pid)"
    existing_job="$(read_lock_field job)"
    echo "[$(date)] LOCK_WAIT_TIMEOUT job=${JOB_NAME} active_pid=${existing_pid:-UNKNOWN} active_job=${existing_job:-UNKNOWN} waited_seconds=${waited}" | tee -a "${LOG_FILE}"
    exit 75
  fi
fi

{
  echo "pid=$$"
  echo "job=${JOB_NAME}"
  echo "started_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "lock_policy=${LOCK_POLICY}"
} > "${LOCK_META}"

run_cmd() {
  echo "[$(date)] RUN: $*" | tee -a "${LOG_FILE}"
  "$@" 2>&1 | tee -a "${LOG_FILE}"
}

cd "${PROJECT_DIR}"
echo "================================================================" | tee -a "${LOG_FILE}"
echo "[$(date)] START job=${JOB_NAME} lock_policy=${LOCK_POLICY}" | tee -a "${LOG_FILE}"
