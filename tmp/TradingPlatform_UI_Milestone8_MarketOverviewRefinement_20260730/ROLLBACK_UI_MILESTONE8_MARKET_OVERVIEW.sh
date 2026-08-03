#!/usr/bin/env bash
set -euo pipefail
TARGET="${1:-$(pwd)}"; MARKER="$TARGET/.ui_milestone8_last_backup"; [[ -f "$MARKER" ]] || { echo "No UI Milestone 8 backup marker." >&2; exit 1; }; BACKUP="$(cat "$MARKER")"; SRC="$TARGET/ui/workstation/src"
[[ -d "$BACKUP" ]] || { echo "Backup missing: $BACKUP" >&2; exit 1; }
for f in App.tsx MarketOverviewRefinedPage.tsx market-overview-refined.css; do if [[ -f "$BACKUP/$f" ]]; then cp "$BACKUP/$f" "$SRC/$f"; else rm -f "$SRC/$f"; fi; done
rm -f "$TARGET/ui/workstation/tests/ui-milestone8-market-overview.test.mjs" "$MARKER"
echo "UI Milestone 8 rollback complete."
