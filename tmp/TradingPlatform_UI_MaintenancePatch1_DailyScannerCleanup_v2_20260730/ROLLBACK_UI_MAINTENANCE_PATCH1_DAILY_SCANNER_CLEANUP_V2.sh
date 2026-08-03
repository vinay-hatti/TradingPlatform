#!/usr/bin/env bash
set -euo pipefail
ROOT="${1:-$(pwd)}"
TARGET="$ROOT/ui/workstation/src/pages.tsx"
BACKUP_ROOT="$ROOT/.ui-maintenance-backups/daily-scanner-cleanup-v2"
LATEST_FILE="$BACKUP_ROOT/LATEST"
[[ -f "$LATEST_FILE" ]] || { echo "ERROR: No recorded backup found at $LATEST_FILE" >&2; exit 1; }
BACKUP_DIR="$(cat "$LATEST_FILE")"
BACKUP="$BACKUP_DIR/pages.tsx"
[[ -f "$BACKUP" ]] || { echo "ERROR: Backup file missing: $BACKUP" >&2; exit 1; }
cp "$BACKUP" "$TARGET"
echo "Rolled back Daily Scanner cleanup v2 from $BACKUP"
