#!/usr/bin/env bash
set -euo pipefail
TARGET="${1:-/Users/vinay.hatti/TradingPlatform}"
MARKER="$TARGET/.last_execution_workspace_ui_recovery_backup"
test -f "$MARKER" || { echo "No recovery backup marker found." >&2; exit 1; }
BACKUP="$(cat "$MARKER")"
test -d "$BACKUP" || { echo "Backup directory missing: $BACKUP" >&2; exit 1; }
cp -R "$BACKUP"/. "$TARGET"/
rm -f "$MARKER"
echo "Execution Workspace UI recovery cleanup rolled back from $BACKUP"
