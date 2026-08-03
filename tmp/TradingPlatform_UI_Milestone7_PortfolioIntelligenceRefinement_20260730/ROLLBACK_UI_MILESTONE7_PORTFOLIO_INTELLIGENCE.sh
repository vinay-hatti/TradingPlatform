#!/usr/bin/env bash
set -euo pipefail
TARGET="${1:-$(pwd)}"
MARKER="$TARGET/.ui_milestone7_last_backup"
[[ -f "$MARKER" ]] || { echo "No UI Milestone 7 backup marker found." >&2; exit 1; }
BACKUP="$(cat "$MARKER")"
[[ -d "$BACKUP" ]] || { echo "Backup not found: $BACKUP" >&2; exit 1; }
SRC_DIR="$TARGET/ui/workstation/src"
for file in App.tsx api.ts types.ts PortfolioIntelligenceRefinedPage.tsx portfolio-intelligence-refined.css; do
  if [[ -f "$BACKUP/$file" ]]; then cp "$BACKUP/$file" "$SRC_DIR/$file"; else rm -f "$SRC_DIR/$file"; fi
done
rm -f "$TARGET/ui/workstation/tests/ui-milestone7-portfolio-intelligence.test.mjs"
echo "UI Milestone 7 rollback completed from $BACKUP"
