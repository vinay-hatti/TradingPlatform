#!/usr/bin/env bash
set -euo pipefail
TARGET="${1:-}"
if [[ -z "$TARGET" || ! -d "$TARGET" ]]; then echo "Usage: $0 /path/to/TradingPlatform" >&2; exit 2; fi
MARKER="$TARGET/.milestone59_last_backup"
if [[ ! -f "$MARKER" ]]; then echo "No Milestone 59 backup marker found." >&2; exit 3; fi
BACKUP="$(cat "$MARKER")"
if [[ ! -d "$BACKUP" ]]; then echo "Backup not found: $BACKUP" >&2; exit 4; fi
cp -a "$BACKUP/." "$TARGET/"
echo "Restored files from $BACKUP"
echo "Database downgrade, if desired: uv run alembic downgrade 20260730_m58"
