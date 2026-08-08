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
