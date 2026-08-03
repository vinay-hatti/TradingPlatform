#!/usr/bin/env bash
set -euo pipefail
ROOT="${1:-/Users/vinay.hatti/TradingPlatform}"
BACKUP="${2:-}"
if [[ -z "$BACKUP" ]]; then
  BACKUP=$(ls -dt "$ROOT"/backups/legacy_risk_positions_exits_cleanup_* 2>/dev/null | head -1 || true)
fi
[[ -n "$BACKUP" && -d "$BACKUP" ]] || { echo "Backup not found"; exit 1; }
for rel in ui/workstation/src/App.tsx ui/workstation/src/WorkspaceChrome.tsx ui/workstation/src/pages.tsx src/trading_ai/production_api/router.py; do
  cp "$BACKUP/$rel" "$ROOT/$rel"
done
rm -f "$ROOT/LEGACY_RISK_POSITIONS_EXITS_CLEANUP_APPLIED.txt"
echo "Rollback completed from $BACKUP"
