#!/usr/bin/env bash
set -euo pipefail
TARGET="${1:-$(pwd)}"
DEST="$TARGET/ui/workstation/src/MarketOverviewRefinedPage.tsx"
BACKUP="$TARGET/.ui_milestone8_nullability_fix_backup/MarketOverviewRefinedPage.tsx"
if [[ ! -f "$BACKUP" ]]; then echo "Backup not found: $BACKUP" >&2; exit 1; fi
cp "$BACKUP" "$DEST"
echo "UI Milestone 8 nullability fix rolled back."
