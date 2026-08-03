#!/usr/bin/env bash
set -euo pipefail
TARGET="${1:-$(pwd)}"
HERE="$(cd "$(dirname "$0")" && pwd)"
STAMP="$(date +%Y%m%dT%H%M%S)"
BACKUP="$TARGET/backups/m57_$STAMP"
mkdir -p "$BACKUP"
while IFS= read -r -d '' src; do
  rel="${src#$HERE/files/}"; dst="$TARGET/$rel"; mkdir -p "$(dirname "$dst")"
  if [ -e "$dst" ]; then mkdir -p "$BACKUP/$(dirname "$rel")"; cp -a "$dst" "$BACKUP/$rel"; fi
  cp -a "$src" "$dst"
done < <(find "$HERE/files" -type f -print0)
cat > "$BACKUP/ROLLBACK.sh" <<ROLL
#!/usr/bin/env bash
set -euo pipefail
while IFS= read -r -d '' src; do rel="\${src#$BACKUP/}"; [ "\$rel" = "ROLLBACK.sh" ] && continue; mkdir -p "$TARGET/\$(dirname "\$rel")"; cp -a "\$src" "$TARGET/\$rel"; done < <(find "$BACKUP" -type f -print0)
ROLL
chmod +x "$BACKUP/ROLLBACK.sh"
echo "Applied Milestone 57 to $TARGET"
echo "Backup: $BACKUP"
echo "Run: cd $TARGET && uv run alembic upgrade head"
