#!/usr/bin/env bash
set -euo pipefail
ROOT="${1:-/Users/vinay.hatti/TradingPlatform}"
HERE="$(cd "$(dirname "$0")" && pwd)"
SRC="$ROOT/ui/workstation/src"
[ -d "$SRC" ] || { echo "Missing $SRC" >&2; exit 1; }
current_pages="$(shasum -a 256 "$SRC/pages.tsx" | awk '{print $1}')"
current_styles="$(shasum -a 256 "$SRC/styles.css" | awk '{print $1}')"
if [[ "$current_pages" == "1b03377170de6cb7f64a4867d47f42506e876c06da6e56979b268c1bad9430d0" && "$current_styles" == "78ee69405eb0a38f61368032054d6350f479cb6862e0e967566c253df1df9f36" ]]; then
  echo "UI Maintenance Patch 3 is already applied."
  exit 0
fi
if [[ "$current_pages" != "587495236eaf818db755347202e341bf2ef56acae3217c366b7e6aa83cf3fc13" || "$current_styles" != "3d5bc9a4c8a0acfaa1b01573f09da5a832b14ae598ba883a7b527ef5f62e135d" ]]; then
  echo "Current Option Scanner files do not match the UI Maintenance Patch 2 baseline." >&2
  echo "pages.tsx: $current_pages" >&2
  echo "styles.css: $current_styles" >&2
  echo "Upload the current src folder before applying this full-file replacement." >&2
  exit 1
fi
BACKUP="$ROOT/.ui_backups/maintenance_patch3_option_scanner_status_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BACKUP"
cp "$SRC/pages.tsx" "$BACKUP/pages.tsx"
cp "$SRC/styles.css" "$BACKUP/styles.css"
cp "$HERE/payload/ui/workstation/src/pages.tsx" "$SRC/pages.tsx"
cp "$HERE/payload/ui/workstation/src/styles.css" "$SRC/styles.css"
printf '%s\n' "$BACKUP" > "$ROOT/.ui_maintenance_patch3_last_backup"
echo "Applied UI Maintenance Patch 3 — Option Scanner persisted-data status fix."
echo "Backup: $BACKUP"
