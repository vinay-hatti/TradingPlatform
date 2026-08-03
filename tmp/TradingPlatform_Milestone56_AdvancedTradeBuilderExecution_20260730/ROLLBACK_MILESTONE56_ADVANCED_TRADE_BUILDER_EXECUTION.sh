#!/usr/bin/env bash
set -euo pipefail
TARGET="${1:-$(pwd)}"
MARKER="$TARGET/.m56_last_backup"
[[ -f "$MARKER" ]] || { echo "No Milestone 56 backup marker found" >&2; exit 1; }
BACKUP="$(cat "$MARKER")"
[[ -d "$BACKUP" ]] || { echo "Backup missing: $BACKUP" >&2; exit 1; }
cp -a "$BACKUP/." "$TARGET/"
echo "Files restored from $BACKUP"
echo "To roll back schema: cd $TARGET && uv run alembic downgrade m55_iif_20260730"
