#!/usr/bin/env bash
set -euo pipefail
ROOT="${1:-/Users/vinay.hatti/TradingPlatform}"
HERE="$(cd "$(dirname "$0")" && pwd)"
SRC="$ROOT/ui/workstation/src"
[ -d "$SRC" ] || { echo "Missing $SRC" >&2; exit 1; }
BACKUP="$ROOT/.ui_backups/maintenance_patch2_option_scanner_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BACKUP"
cp "$SRC/pages.tsx" "$BACKUP/pages.tsx"
cp "$SRC/styles.css" "$BACKUP/styles.css"
cp "$HERE/payload/ui/workstation/src/pages.tsx" "$SRC/pages.tsx"
cp "$HERE/payload/ui/workstation/src/styles.css" "$SRC/styles.css"
printf '%s\n' "$BACKUP" > "$ROOT/.ui_maintenance_patch2_last_backup"
echo "Applied UI Maintenance Patch 2"
echo "Backup: $BACKUP"
