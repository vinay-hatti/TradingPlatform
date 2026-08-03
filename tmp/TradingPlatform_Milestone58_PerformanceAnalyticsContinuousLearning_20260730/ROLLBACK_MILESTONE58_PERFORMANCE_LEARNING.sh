#!/usr/bin/env bash
set -euo pipefail
TARGET="${1:-$(pwd)}";MARKER="$TARGET/.milestone_backups/m58_last_backup";[ -f "$MARKER" ]||{ echo 'No M58 backup marker';exit 1;};BACKUP="$(cat "$MARKER")"
while IFS= read -r -d '' src;do rel="${src#$BACKUP/}";mkdir -p "$(dirname "$TARGET/$rel")";cp "$src" "$TARGET/$rel";done < <(find "$BACKUP" -type f -print0)
echo 'Restore complete. Downgrade database explicitly only after preserving M58 data: uv run alembic downgrade 20260730_m57'
