#!/usr/bin/env bash
set -euo pipefail
TARGET="${1:-$(pwd)}";ROOT="$(cd "$(dirname "$0")" && pwd)";BACKUP="$TARGET/.milestone_backups/m58_$(date +%Y%m%d_%H%M%S)";mkdir -p "$BACKUP"
while IFS= read -r -d '' src; do rel="${src#$ROOT/files/}";dst="$TARGET/$rel";mkdir -p "$(dirname "$dst")";if [ -f "$dst" ];then mkdir -p "$BACKUP/$(dirname "$rel")";cp "$dst" "$BACKUP/$rel";fi;cp "$src" "$dst";done < <(find "$ROOT/files" -type f -print0)
echo "$BACKUP" > "$TARGET/.milestone_backups/m58_last_backup"
echo "Milestone 58 files applied. Run: uv run alembic upgrade head"
