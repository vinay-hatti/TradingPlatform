#!/usr/bin/env bash
set -euo pipefail
ROOT="${1:-/Users/vinay.hatti/TradingPlatform}"
MARKER="$ROOT/.ui_maintenance_patch3_last_backup"
[ -f "$MARKER" ] || { echo "No Patch 3 backup marker found." >&2; exit 1; }
BACKUP="$(cat "$MARKER")"
[ -f "$BACKUP/pages.tsx" ] && cp "$BACKUP/pages.tsx" "$ROOT/ui/workstation/src/pages.tsx"
[ -f "$BACKUP/styles.css" ] && cp "$BACKUP/styles.css" "$ROOT/ui/workstation/src/styles.css"
rm -f "$MARKER"
echo "Rolled back UI Maintenance Patch 3 from $BACKUP"
