#!/usr/bin/env bash
set -euo pipefail
ROOT="${1:-/Users/vinay.hatti/TradingPlatform}"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
BACKUP="$ROOT/.ui_patch_backups/daily_scanner_cleanup_20260730_$STAMP"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
python3 "$SCRIPT_DIR/patch_daily_scanner.py" "$ROOT" --backup-root "$BACKUP"
mkdir -p "$ROOT/ui/workstation/tests"
cp "$SCRIPT_DIR/tests/daily-scanner-workflow-cleanup.test.mjs" "$ROOT/ui/workstation/tests/"
echo "$BACKUP" > "$ROOT/.ui_patch_backups/latest_daily_scanner_cleanup_backup.txt"
echo "Applied Daily Scanner workflow cleanup. Backup: $BACKUP"
