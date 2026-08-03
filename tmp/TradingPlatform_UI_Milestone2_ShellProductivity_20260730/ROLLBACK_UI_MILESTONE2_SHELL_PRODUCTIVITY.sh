#!/usr/bin/env bash
set -euo pipefail
TARGET="${1:-$(pwd)}"
BACKUP="$TARGET/.ui_milestone2_backup"
[[ -d "$BACKUP" ]] || { echo "ERROR: No UI Milestone 2 backup found at $BACKUP" >&2; exit 1; }
for file in App.tsx WorkspaceChrome.tsx WorkspaceProductivity.tsx styles.css; do
  if [[ -f "$BACKUP/ui/workstation/src/$file" ]]; then cp "$BACKUP/ui/workstation/src/$file" "$TARGET/ui/workstation/src/$file"; else rm -f "$TARGET/ui/workstation/src/$file"; fi
done
for file in design-system.test.mjs workspace-productivity.test.mjs; do
  if [[ -f "$BACKUP/ui/workstation/tests/$file" ]]; then cp "$BACKUP/ui/workstation/tests/$file" "$TARGET/ui/workstation/tests/$file"; else rm -f "$TARGET/ui/workstation/tests/$file"; fi
done
echo "UI Milestone 2 source files rolled back. PROJECT_STATUS.md is intentionally not rewritten automatically."
