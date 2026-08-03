#!/usr/bin/env bash
set -euo pipefail
TARGET="${1:-$(pwd)}"
MARKER="$TARGET/.ui_shell_recovery_last_backup"
[[ -f "$MARKER" ]] || { echo "No UI shell recovery backup marker found." >&2; exit 1; }
BACKUP="$(cat "$MARKER")"
cp "$BACKUP/ui/workstation/src/App.tsx" "$TARGET/ui/workstation/src/App.tsx"
cp "$BACKUP/ui/workstation/src/styles.css" "$TARGET/ui/workstation/src/styles.css"
for f in WorkstationRouteBoundary.tsx workstation-shell-recovery.css; do
  if [[ -f "$BACKUP/ui/workstation/src/$f" ]]; then cp "$BACKUP/ui/workstation/src/$f" "$TARGET/ui/workstation/src/$f"; else rm -f "$TARGET/ui/workstation/src/$f"; fi
done
rm -f "$TARGET/ui/workstation/tests/workstation-shell-recovery.test.mjs"
rm -f "$MARKER"
echo "UI shell recovery fix rolled back from $BACKUP"
