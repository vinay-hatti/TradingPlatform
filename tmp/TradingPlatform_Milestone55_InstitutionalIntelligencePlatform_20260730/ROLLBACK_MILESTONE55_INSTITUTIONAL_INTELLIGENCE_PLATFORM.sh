#!/usr/bin/env bash
set -euo pipefail
TARGET="${1:-$(pwd)}"; [[ -f "$TARGET/.m55_last_backup" ]] || { echo "No Milestone 55 backup marker"; exit 1; }; BACKUP="$(cat "$TARGET/.m55_last_backup")"
uv run alembic downgrade m54_001 || true
cp -R "$BACKUP"/. "$TARGET"/
echo "Rolled back Milestone 55 files from $BACKUP"
