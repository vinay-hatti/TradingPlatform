#!/usr/bin/env bash
set -euo pipefail
TARGET="${1:-$(pwd)}"
MARKER="$TARGET/.m54_phase3_last_backup"
[[ -f "$MARKER" ]] || { echo "No Phase 3 backup marker found" >&2; exit 1; }
BACKUP="$(cat "$MARKER")"
[[ -d "$BACKUP" ]] || { echo "Backup directory not found: $BACKUP" >&2; exit 1; }
cp -a "$BACKUP"/. "$TARGET"/
echo "Rolled back Milestone 54 Phase 3 from $BACKUP"
