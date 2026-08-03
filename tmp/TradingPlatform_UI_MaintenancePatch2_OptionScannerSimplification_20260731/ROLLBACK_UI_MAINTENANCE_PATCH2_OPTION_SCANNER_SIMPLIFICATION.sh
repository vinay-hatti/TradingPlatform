#!/usr/bin/env bash
set -euo pipefail
ROOT="${1:-/Users/vinay.hatti/TradingPlatform}"
MARKER="$ROOT/.ui_maintenance_patch2_last_backup"
[ -f "$MARKER" ] || { echo "No rollback marker found" >&2; exit 1; }
BACKUP="$(cat "$MARKER")"
cp "$BACKUP/pages.tsx" "$ROOT/ui/workstation/src/pages.tsx"
cp "$BACKUP/styles.css" "$ROOT/ui/workstation/src/styles.css"
echo "Rolled back UI Maintenance Patch 2 from $BACKUP"
