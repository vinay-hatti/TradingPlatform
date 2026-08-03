#!/usr/bin/env bash
set -euo pipefail
TARGET="${1:-$(pwd)}"
MARKER="$TARGET/.m53_phase1_last_backup"
[[ -f "$MARKER" ]] || { echo "No Phase 1 backup marker found: $MARKER" >&2; exit 1; }
BACKUP="$(cat "$MARKER")"
[[ -d "$BACKUP" ]] || { echo "Backup directory not found: $BACKUP" >&2; exit 1; }
while IFS= read -r -d '' file; do
  rel="${file#$BACKUP/}"
  mkdir -p "$TARGET/$(dirname "$rel")"
  cp "$file" "$TARGET/$rel"
done < <(find "$BACKUP" -type f -print0)
rm -f "$TARGET/ui/workstation/src"/OptionScannerPage.tsx 2>/dev/null || true
rm -f "$MARKER"
echo "Rolled back Milestone 53 Phase 1 from $BACKUP"
