#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

mkdir -p logs reports/m69_event_intelligence
LOG_FILE="$ROOT/logs/m69_6_daily_event_intelligence.log"
STATUS_FILE="$ROOT/reports/m69_event_intelligence/daily_latest.json"
LOCK_DIR="$ROOT/reports/m69_event_intelligence/daily.lock"
STARTED_AT="$(date -u +%FT%TZ)"
DEGRADED=0

# launchd does not inherit interactive shell exports. Load governed local env files
# when present. These files are never created or modified by this script.
for env_file in \
  "$ROOT/.env" \
  "$HOME/.config/tradingplatform/m69_6.env"
do
  if [[ -f "$env_file" ]]; then
    set -a
    # shellcheck disable=SC1090
    source "$env_file"
    set +a
  fi
done

resolve_uv() {
  if [[ -n "${UV_BIN:-}" && -x "${UV_BIN}" ]]; then
    printf '%s\n' "$UV_BIN"
    return 0
  fi
  local candidate
  for candidate in \
    "$(command -v uv 2>/dev/null || true)" \
    "/opt/homebrew/bin/uv" \
    "/usr/local/bin/uv" \
    "$HOME/.local/bin/uv" \
    "$HOME/.cargo/bin/uv"
  do
    if [[ -n "$candidate" && -x "$candidate" ]]; then
      printf '%s\n' "$candidate"
      return 0
    fi
  done
  return 1
}

UV="$(resolve_uv)" || {
  echo "[$(date -u +%FT%TZ)] ERROR: uv executable not found" | tee -a "$LOG_FILE"
  exit 127
}

# Prevent overlapping daily runs. Clear a stale lock only when its recorded PID
# is no longer alive.
if ! mkdir "$LOCK_DIR" 2>/dev/null; then
  if [[ -f "$LOCK_DIR/pid" ]]; then
    old_pid="$(cat "$LOCK_DIR/pid" 2>/dev/null || true)"
    if [[ -n "$old_pid" ]] && ! kill -0 "$old_pid" 2>/dev/null; then
      rm -rf "$LOCK_DIR"
      mkdir "$LOCK_DIR"
    else
      echo "[$(date -u +%FT%TZ)] M69.6 daily event intelligence already running" | tee -a "$LOG_FILE"
      exit 0
    fi
  else
    echo "[$(date -u +%FT%TZ)] M69.6 daily event intelligence lock exists" | tee -a "$LOG_FILE"
    exit 0
  fi
fi
printf '%s\n' "$$" > "$LOCK_DIR/pid"
trap 'rm -rf "$LOCK_DIR"' EXIT INT TERM

run_stage() {
  local name="$1"
  shift
  echo "[$(date -u +%FT%TZ)] START $name"
  "$@"
  echo "[$(date -u +%FT%TZ)] COMPLETE $name"
}

# Reconciliation is intentionally guarded. A transient Fed/BEA source failure
# must never invalidate the last verified macro registry.
run_guarded_reconciliation() {
  local start_year="${M69_6_MACRO_START_YEAR:-2016}"
  local dry_file
  dry_file="$(mktemp "$ROOT/reports/m69_event_intelligence/reconcile_dry_run.XXXXXX.json")"

  echo "[$(date -u +%FT%TZ)] START macro integrity dry-run"
  if ! "$UV" run python scripts/reconcile_m69_macro_event_integrity.py \
      --start-year "$start_year" | tee "$dry_file"; then
    echo "[$(date -u +%FT%TZ)] DEGRADED: macro integrity dry-run failed; retaining last verified registry"
    rm -f "$dry_file"
    DEGRADED=1
    return 0
  fi

  if ! python3 - "$dry_file" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
raw = path.read_text(encoding="utf-8")
start = raw.find("{")
if start < 0:
    raise SystemExit(2)
data = json.loads(raw[start:])
completed = int(data.get("authoritative_completed_fomc_dates", 0))
future = int(data.get("authoritative_future_fomc_dates", 0))
bea = int(data.get("authoritative_bea_releases", 0))
# Broad sanity bounds protect against empty/partial downloads while allowing
# genuine schedule changes and future years.
if not (70 <= completed <= 120):
    raise SystemExit(3)
if future < 1:
    raise SystemExit(4)
if bea < 250:
    raise SystemExit(5)
PY
  then
    echo "[$(date -u +%FT%TZ)] DEGRADED: authoritative macro counts failed safety checks; reconciliation apply skipped"
    rm -f "$dry_file"
    DEGRADED=1
    return 0
  fi

  rm -f "$dry_file"
  run_stage "macro integrity reconciliation" \
    "$UV" run python scripts/reconcile_m69_macro_event_integrity.py \
      --start-year "$start_year" --apply
}

{
  echo "[$STARTED_AT] M69.6 automated event intelligence start"
  echo "[$STARTED_AT] project_root=$ROOT uv=$UV"

  run_stage "six-month event calendar synchronization" \
    "$UV" run python scripts/sync_m69_event_calendar.py --horizon-months 6

  run_guarded_reconciliation

  run_stage "completed event outcome realization" \
    "$UV" run python scripts/realize_m69_event_outcomes.py

  # This command recomputes governed expected moves and captures the immutable
  # pre-event forecast snapshot for the current business date.
  run_stage "expected moves and forecast snapshots" \
    "$UV" run python scripts/compute_m69_event_expected_moves.py

  run_stage "event intelligence acceptance verification" \
    "$UV" run python scripts/verify_m69_event_intelligence_hardening.py

  COMPLETED_AT="$(date -u +%FT%TZ)"
  FINAL_STATUS="READY"
  if [[ "$DEGRADED" -ne 0 ]]; then
    FINAL_STATUS="DEGRADED"
  fi
  python3 - "$STATUS_FILE" "$STARTED_AT" "$COMPLETED_AT" "$FINAL_STATUS" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
payload = {
    "status": sys.argv[4],
    "started_at": sys.argv[2],
    "completed_at": sys.argv[3],
    "schedule": "DAILY_08_30_LOCAL",
    "horizon_months": 6,
    "macro_start_year": 2016,
    "stages": [
        "event_calendar_sync",
        "guarded_macro_integrity_reconciliation",
        "event_outcome_realization",
        "expected_move_and_forecast_snapshot_refresh",
        "acceptance_verification",
    ],
}
path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY
  echo "[$COMPLETED_AT] M69.6 automated event intelligence complete status=$FINAL_STATUS"
} 2>&1 | tee -a "$LOG_FILE"
