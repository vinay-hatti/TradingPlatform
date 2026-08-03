#!/usr/bin/env bash
set -euo pipefail
TARGET="${1:-/Users/vinay.hatti/TradingPlatform}"
HERE="$(cd "$(dirname "$0")" && pwd)"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
BACKUP="$TARGET/backups/execution_workspace_ui_recovery_cleanup_$STAMP"
FILES=(
  ui/workstation/src/App.tsx
  ui/workstation/src/WorkspaceChrome.tsx
  ui/workstation/src/pages.tsx
  ui/workstation/src/api.ts
  ui/workstation/src/ExecutionWorkspacePage.tsx
  src/trading_ai/production_api/router.py
)
mkdir -p "$BACKUP"
for rel in "${FILES[@]}"; do
  test -f "$TARGET/$rel" || { echo "Missing target file: $TARGET/$rel" >&2; exit 1; }
  mkdir -p "$BACKUP/$(dirname "$rel")"
  cp "$TARGET/$rel" "$BACKUP/$rel"
  mkdir -p "$TARGET/$(dirname "$rel")"
  cp "$HERE/files/$rel" "$TARGET/$rel"
done
printf '%s\n' "$BACKUP" > "$TARGET/.last_execution_workspace_ui_recovery_backup"
echo "Execution Workspace UI recovery cleanup applied."
echo "Backup: $BACKUP"
echo "Restart backend and workstation, then hard-refresh the browser."
