#!/usr/bin/env bash
set -euo pipefail
TARGET="${1:-$(pwd)}"; HERE="$(cd "$(dirname "$0")" && pwd)"; TS="$(date +%Y%m%dT%H%M%S)"; BACKUP="$TARGET/backups/m55_$TS"
mkdir -p "$BACKUP"
while IFS= read -r -d '' src; do rel="${src#$HERE/files/}"; dst="$TARGET/$rel"; mkdir -p "$(dirname "$dst")"; if [[ -f "$dst" ]]; then mkdir -p "$BACKUP/$(dirname "$rel")"; cp "$dst" "$BACKUP/$rel"; fi; cp "$src" "$dst"; done < <(find "$HERE/files" -type f -print0)
echo "$BACKUP" > "$TARGET/.m55_last_backup"
echo "Applied Milestone 55. Next: uv run alembic upgrade head; PYTHONPATH=src uv run python scripts/test_m55_institutional_intelligence_platform.py; cd ui/workstation && rm -rf node_modules && npm ci && npm run typecheck && npm test && npm run build"
