#!/usr/bin/env bash
set -euo pipefail
TARGET="${1:-$(pwd)}"
PACKAGE_DIR="$(cd "$(dirname "$0")" && pwd)"
BACKUP_DIR="$TARGET/.m53_phase2_option_scanner_backup_$(date +%Y%m%d_%H%M%S)"
FILES=(
  "ui/workstation/src/pages.tsx"
  "ui/workstation/src/styles.css"
)
mkdir -p "$BACKUP_DIR"
for file in "${FILES[@]}"; do
  if [[ ! -f "$TARGET/$file" ]]; then
    echo "Missing target file: $TARGET/$file" >&2
    exit 1
  fi
  mkdir -p "$BACKUP_DIR/$(dirname "$file")" "$TARGET/$(dirname "$file")"
  cp "$TARGET/$file" "$BACKUP_DIR/$file"
  cp "$PACKAGE_DIR/$file" "$TARGET/$file"
done
mkdir -p "$TARGET/scripts"
cp "$PACKAGE_DIR/scripts/test_m53_phase2_option_scanner_workspace.py" "$TARGET/scripts/"
printf '%s\n' "$BACKUP_DIR" > "$TARGET/.m53_phase2_option_scanner_last_backup"
echo "Milestone 53 Phase 2 applied."
echo "Backup: $BACKUP_DIR"
