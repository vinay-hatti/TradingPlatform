#!/usr/bin/env bash
set -euo pipefail
TARGET="${1:-$(pwd)}"; SRC="$TARGET/ui/workstation/src"; BACKUP="$TARGET/.ui_milestone6_backup"
[[ -f "$BACKUP/App.tsx" ]] && cp "$BACKUP/App.tsx" "$SRC/App.tsx"
for f in AdvancedTradeBuilderRefinedPage.tsx advanced-trade-builder-refined.css; do if [[ -f "$BACKUP/$f" ]]; then cp "$BACKUP/$f" "$SRC/$f"; else rm -f "$SRC/$f"; fi; done
rm -f "$TARGET/ui/workstation/tests/ui-milestone6-advanced-trade-builder.test.mjs"
echo "UI Milestone 6 rolled back."
