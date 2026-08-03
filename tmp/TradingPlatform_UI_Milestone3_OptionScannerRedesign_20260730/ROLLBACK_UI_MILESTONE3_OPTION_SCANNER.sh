#!/usr/bin/env bash
set -euo pipefail
TARGET="${1:-$(pwd)}"
LATEST="$(find "$TARGET/backups" -maxdepth 1 -type d -name 'ui_milestone3_option_scanner_*' 2>/dev/null | sort | tail -1)"
[ -n "$LATEST" ] && [ -x "$LATEST/ROLLBACK.sh" ] || { echo "No UI Milestone 3 backup found." >&2; exit 1; }
exec "$LATEST/ROLLBACK.sh"
