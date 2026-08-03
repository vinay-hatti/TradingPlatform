#!/usr/bin/env bash
set -euo pipefail
TARGET="${1:-$(pwd)}"; SRC="$TARGET/ui/workstation/src"; BACKUP="$TARGET/.ui_milestone5_backup"
if [[ -f "$BACKUP/App.tsx" ]]; then cp "$BACKUP/App.tsx" "$SRC/App.tsx"; fi
for f in InstitutionalIntelligenceRefinedPage.tsx institutional-intelligence-refined.css; do if [[ -f "$BACKUP/$f" ]]; then cp "$BACKUP/$f" "$SRC/$f"; else rm -f "$SRC/$f"; fi; done
rm -f "$TARGET/ui/workstation/tests/ui-milestone5-institutional-intelligence.test.mjs"
echo "UI Milestone 5 rolled back."
