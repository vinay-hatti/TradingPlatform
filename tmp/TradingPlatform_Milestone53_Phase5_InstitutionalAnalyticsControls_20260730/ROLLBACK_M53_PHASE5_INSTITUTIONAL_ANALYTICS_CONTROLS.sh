#!/usr/bin/env bash
set -euo pipefail
ROOT="${1:-$(pwd)}"
MARKER="$ROOT/.m53_phase5_last_backup"
[[ -f "$MARKER" ]] || { echo "No Phase 5 backup marker found." >&2; exit 1; }
BACKUP="$(cat "$MARKER")"
[[ -d "$BACKUP" ]] || { echo "Backup not found: $BACKUP" >&2; exit 1; }
cd "$BACKUP"
find . -type f -print0 | while IFS= read -r -d '' file; do
  rel="${file#./}"; mkdir -p "$ROOT/$(dirname "$rel")"; cp -p "$file" "$ROOT/$rel"
done
echo "Rolled back Milestone 53 Phase 5 from $BACKUP"
