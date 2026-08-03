#!/usr/bin/env bash
set -euo pipefail
TARGET="${1:-$(pwd)}"
PKG_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
STAMP="$(date +%Y%m%d_%H%M%S)"
BACKUP="$TARGET/.m53_phase1_backup_$STAMP"
FILES=(
  "ui/workstation/src/App.tsx"
  "ui/workstation/src/pages.tsx"
  "ui/workstation/src/types.ts"
  "scripts/test_m53_phase1_option_scanner_workspace.py"
)
mkdir -p "$BACKUP"
for rel in "${FILES[@]}"; do
  if [[ -f "$TARGET/$rel" ]]; then
    mkdir -p "$BACKUP/$(dirname "$rel")"
    cp "$TARGET/$rel" "$BACKUP/$rel"
  fi
  mkdir -p "$TARGET/$(dirname "$rel")"
  cp "$PKG_DIR/$rel" "$TARGET/$rel"
done
printf '%s\n' "$BACKUP" > "$TARGET/.m53_phase1_last_backup"
echo "Applied Milestone 53 Phase 1 Option Scanner workspace."
echo "Backup: $BACKUP"
echo "Validate: cd $TARGET/ui/workstation && npm run typecheck && npm test"
echo "Contract: PYTHONPATH=src uv run python scripts/test_m53_phase1_option_scanner_workspace.py"
