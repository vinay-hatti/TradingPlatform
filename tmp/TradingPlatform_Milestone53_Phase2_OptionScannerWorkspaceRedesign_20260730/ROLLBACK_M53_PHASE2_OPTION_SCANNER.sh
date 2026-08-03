#!/usr/bin/env bash
set -euo pipefail
TARGET="${1:-$(pwd)}"
MARKER="$TARGET/.m53_phase2_option_scanner_last_backup"
if [[ ! -f "$MARKER" ]]; then
  echo "No Phase 2 backup marker found: $MARKER" >&2
  exit 1
fi
BACKUP_DIR="$(cat "$MARKER")"
FILES=(
  "ui/workstation/src/pages.tsx"
  "ui/workstation/src/styles.css"
)
for file in "${FILES[@]}"; do
  if [[ ! -f "$BACKUP_DIR/$file" ]]; then
    echo "Missing backup file: $BACKUP_DIR/$file" >&2
    exit 1
  fi
  cp "$BACKUP_DIR/$file" "$TARGET/$file"
done
rm -f "$TARGET/scripts/test_m53_phase2_option_scanner_workspace.py" "$MARKER"
echo "Milestone 53 Phase 2 rolled back from $BACKUP_DIR"
