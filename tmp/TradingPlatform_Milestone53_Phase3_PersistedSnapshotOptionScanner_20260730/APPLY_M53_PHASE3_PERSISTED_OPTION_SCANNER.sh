#!/usr/bin/env bash
set -euo pipefail
TARGET="${1:-$(pwd)}"
PACKAGE_DIR="$(cd "$(dirname "$0")" && pwd)"
STAMP="$(date +%Y%m%d_%H%M%S)"
BACKUP="$TARGET/.m53_phase3_backup_$STAMP"
mkdir -p "$BACKUP/ui/workstation/src"
for file in pages.tsx styles.css; do
  if [[ -f "$TARGET/ui/workstation/src/$file" ]]; then
    cp "$TARGET/ui/workstation/src/$file" "$BACKUP/ui/workstation/src/$file"
  fi
done
cp "$PACKAGE_DIR/ui/workstation/src/pages.tsx" "$TARGET/ui/workstation/src/pages.tsx"
cp "$PACKAGE_DIR/ui/workstation/src/styles.css" "$TARGET/ui/workstation/src/styles.css"
cp "$PACKAGE_DIR/scripts/test_m53_phase3_persisted_snapshot_option_scanner.py" "$TARGET/scripts/test_m53_phase3_persisted_snapshot_option_scanner.py"
printf '%s\n' "$BACKUP" > "$TARGET/.m53_phase3_last_backup"
echo "Applied Milestone 53 Phase 3. Backup: $BACKUP"
