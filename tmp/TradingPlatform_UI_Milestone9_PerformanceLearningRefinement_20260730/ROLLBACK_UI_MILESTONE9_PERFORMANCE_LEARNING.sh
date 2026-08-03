#!/usr/bin/env bash
set -euo pipefail
TARGET="${1:-$(pwd)}"; SRC="$TARGET/ui/workstation/src"; MARKER="$TARGET/.ui_milestone9_last_backup"
[[ -f "$MARKER" ]] || { echo "No UI Milestone 9 backup marker found." >&2; exit 1; }
BACKUP="$(cat "$MARKER")"; [[ -d "$BACKUP" ]] || { echo "Backup missing: $BACKUP" >&2; exit 1; }
for f in App.tsx PerformanceLearningRefinedPage.tsx performance-learning-refined.css; do
  if [[ -f "$BACKUP/$f" ]]; then cp "$BACKUP/$f" "$SRC/$f"; else rm -f "$SRC/$f"; fi
done
rm -f "$TARGET/ui/workstation/tests/ui-milestone9-performance-learning.test.mjs" "$MARKER"
echo "UI Milestone 9 rolled back from $BACKUP"
