#!/usr/bin/env bash
set -euo pipefail
TARGET="${1:-$(pwd)}"
BACKUP_FILE="$TARGET/.ui_milestone1_last_backup"
[[ -f "$BACKUP_FILE" ]] || { echo "ERROR: no UI Milestone 1 backup pointer found"; exit 1; }
BACKUP_DIR="$(cat "$BACKUP_FILE")"
[[ -d "$BACKUP_DIR" ]] || { echo "ERROR: backup directory missing: $BACKUP_DIR"; exit 1; }
for f in App.tsx WorkspaceChrome.tsx styles.css; do
  if [[ -f "$BACKUP_DIR/ui/workstation/src/$f" ]]; then cp "$BACKUP_DIR/ui/workstation/src/$f" "$TARGET/ui/workstation/src/$f"; else rm -f "$TARGET/ui/workstation/src/$f"; fi
done
if [[ -f "$BACKUP_DIR/ui/workstation/tests/design-system.test.mjs" ]]; then
  cp "$BACKUP_DIR/ui/workstation/tests/design-system.test.mjs" "$TARGET/ui/workstation/tests/"
else
  rm -f "$TARGET/ui/workstation/tests/design-system.test.mjs"
fi
echo "UI Milestone 1 rolled back from $BACKUP_DIR"
