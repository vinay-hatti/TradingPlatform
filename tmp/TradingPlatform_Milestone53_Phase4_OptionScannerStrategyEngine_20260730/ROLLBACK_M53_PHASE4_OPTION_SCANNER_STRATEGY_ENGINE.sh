#!/usr/bin/env bash
set -euo pipefail
TARGET="${1:-$(pwd)}"
MARKER="$TARGET/.m53_phase4_last_backup"
[[ -f "$MARKER" ]] || { echo "No Phase 4 backup marker found." >&2; exit 1; }
BACKUP="$(cat "$MARKER")"
[[ -d "$BACKUP" ]] || { echo "Backup directory not found: $BACKUP" >&2; exit 1; }
for file in pages.tsx styles.css; do
  [[ -f "$BACKUP/ui/workstation/src/$file" ]] && cp "$BACKUP/ui/workstation/src/$file" "$TARGET/ui/workstation/src/$file"
done
rm -f "$TARGET/scripts/test_m53_phase4_option_scanner_strategy_engine.py" "$MARKER"
echo "Rolled back Milestone 53 Phase 4 from $BACKUP"
