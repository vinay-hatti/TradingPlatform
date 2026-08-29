#!/bin/bash
set -euo pipefail

PROJECT="/Users/vinay.hatti/TradingPlatform"
UV="/opt/homebrew/bin/uv"
LOG_DIR="$PROJECT/logs/m77_6_shadow"
LOCK_DIR="$PROJECT/run/m77_6_shadow.lock"

mkdir -p "$LOG_DIR" "$PROJECT/run"

ts() { date '+%Y-%m-%d %H:%M:%S %Z'; }

echo "[$(ts)] START m77_6_daily_shadow_collector"

if ! mkdir "$LOCK_DIR" 2>/dev/null; then
  echo "[$(ts)] SKIP already running; lock=$LOCK_DIR"
  exit 0
fi
cleanup() {
  rmdir "$LOCK_DIR" 2>/dev/null || true
}
trap cleanup EXIT

cd "$PROJECT"

# Fail closed unless current Stock Intelligence publication is READY.
READY_JSON="$("$UV" run python - <<'PY'
import json
from sqlalchemy import text
from trading_ai.database.session import SessionLocal

with SessionLocal() as session:
    row = session.execute(text("""
        SELECT scanner_run_id, snapshot_timestamp, status
        FROM stock_scanner_publications
        WHERE publication_name = 'current_stock_intelligence'
        ORDER BY snapshot_timestamp DESC
        LIMIT 1
    """)).mappings().first()

if not row:
    print(json.dumps({"ready": False, "reason": "NO_CURRENT_STOCK_INTELLIGENCE"}))
else:
    print(json.dumps({
        "ready": str(row["status"]).upper() == "READY",
        "status": row["status"],
        "scanner_run_id": row["scanner_run_id"],
        "snapshot_timestamp": str(row["snapshot_timestamp"]),
    }))
PY
)"

echo "[$(ts)] current_stock_intelligence=$READY_JSON"

IS_READY="$(printf '%s' "$READY_JSON" | "$UV" run python -c 'import sys,json; print("1" if json.load(sys.stdin).get("ready") else "0")')"
if [ "$IS_READY" != "1" ]; then
  echo "[$(ts)] SKIP current_stock_intelligence not READY"
  exit 0
fi

"$UV" run python scripts/run_m77_6_live_forward_shadow.py cycle
STATUS=$?

echo "[$(ts)] END m77_6_daily_shadow_collector status=$STATUS"
exit "$STATUS"
