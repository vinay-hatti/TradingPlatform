#!/usr/bin/env bash
set -euo pipefail
TARGET="${1:-$(pwd)}"
HERE="$(cd "$(dirname "$0")" && pwd)"
BACKUP="$TARGET/.rollback/m56_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BACKUP"
while IFS= read -r -d '' src; do
  rel="${src#"$HERE/files/"}"; dst="$TARGET/$rel"; mkdir -p "$(dirname "$dst")"
  if [[ -e "$dst" ]]; then mkdir -p "$BACKUP/$(dirname "$rel")"; cp -p "$dst" "$BACKUP/$rel"; fi
  cp -p "$src" "$dst"
done < <(find "$HERE/files" -type f -print0)
printf '%s\n' "$BACKUP" > "$TARGET/.m56_last_backup"
echo "Milestone 56 files applied to $TARGET"
echo "Backup: $BACKUP"
echo "Next: cd $TARGET && uv run alembic upgrade head"
