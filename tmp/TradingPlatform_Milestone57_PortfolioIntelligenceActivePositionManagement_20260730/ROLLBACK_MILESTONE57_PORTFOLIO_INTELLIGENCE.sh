#!/usr/bin/env bash
set -euo pipefail
TARGET="${1:-$(pwd)}"
LATEST="$(find "$TARGET/backups" -maxdepth 1 -type d -name 'm57_*' | sort | tail -1)"
[ -n "$LATEST" ] || { echo "No Milestone 57 backup found"; exit 1; }
"$LATEST/ROLLBACK.sh"
echo "Rollback files restored from $LATEST"
echo "Database rollback, if required: uv run alembic downgrade 20260730_m56_trade_builder"
