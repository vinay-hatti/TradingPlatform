#!/usr/bin/env bash
set -euo pipefail
TARGET="${1:-$(pwd)}"
SRC_DIR="$(cd "$(dirname "$0")" && pwd)"
DEST="$TARGET/ui/workstation/src/MarketOverviewRefinedPage.tsx"
BACKUP_DIR="$TARGET/.ui_milestone8_nullability_fix_backup"
mkdir -p "$BACKUP_DIR"
if [[ -f "$DEST" ]]; then cp "$DEST" "$BACKUP_DIR/MarketOverviewRefinedPage.tsx"; fi
cp "$SRC_DIR/files/ui/workstation/src/MarketOverviewRefinedPage.tsx" "$DEST"
echo "UI Milestone 8 nullability fix applied. Run npm run typecheck and npm run build in ui/workstation."
