#!/usr/bin/env bash
set -euo pipefail
TARGET="${1:-}"
if [[ -z "$TARGET" || ! -d "$TARGET" ]]; then echo "Usage: $0 /path/to/TradingPlatform" >&2; exit 2; fi
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
BACKUP="$TARGET/backups/milestone59_execution_workspace_$STAMP"
mkdir -p "$BACKUP"
cd "$SCRIPT_DIR/files"
while IFS= read -r -d '' f; do
  rel="${f#./}"; dest="$TARGET/$rel"
  if [[ -e "$dest" ]]; then mkdir -p "$BACKUP/$(dirname "$rel")"; cp -a "$dest" "$BACKUP/$rel"; fi
  mkdir -p "$(dirname "$dest")"; cp -a "$f" "$dest"
done < <(find . -type f -print0)
printf '%s\n' "$BACKUP" > "$TARGET/.milestone59_last_backup"
echo "Applied Milestone 59 to $TARGET"
echo "Backup: $BACKUP"
echo "Next: cd $TARGET && uv run alembic upgrade head"
