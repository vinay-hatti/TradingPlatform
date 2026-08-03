#!/usr/bin/env bash
set -euo pipefail
TARGET="${1:-$(pwd)}"
ROOT="$(cd "$(dirname "$0")" && pwd)"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
BACKUP="$TARGET/backups/m54_phase2_$STAMP"
FILES=(
  src/trading_ai/opportunity_domain
  src/trading_ai/production_api/app.py
  ui/workstation/src/App.tsx
  ui/workstation/src/api.ts
  ui/workstation/src/pages.tsx
  ui/workstation/src/styles.css
  ui/workstation/src/types.ts
  migrations/versions/m54_001_canonical_opportunity_domain.py
  scripts/test_m54_phase2_institutional_opportunity_workspace.py
  src/trading_ai/database/models.py
)
mkdir -p "$BACKUP"
for path in "${FILES[@]}"; do
  if [ -e "$TARGET/$path" ]; then
    mkdir -p "$BACKUP/$(dirname "$path")"
    cp -R "$TARGET/$path" "$BACKUP/$path"
  fi
done
mkdir -p "$TARGET/src/trading_ai/opportunity_domain" "$TARGET/src/trading_ai/production_api" "$TARGET/ui/workstation/src" "$TARGET/migrations/versions" "$TARGET/scripts"
cp -R "$ROOT/src/trading_ai/opportunity_domain/." "$TARGET/src/trading_ai/opportunity_domain/"
cp "$ROOT/src/trading_ai/production_api/app.py" "$TARGET/src/trading_ai/production_api/app.py"
cp "$ROOT/ui/workstation/src/"* "$TARGET/ui/workstation/src/"
cp "$ROOT/migrations/versions/m54_001_canonical_opportunity_domain.py" "$TARGET/migrations/versions/"
cp "$ROOT/scripts/test_m54_phase2_institutional_opportunity_workspace.py" "$TARGET/scripts/"
if ! grep -q "trading_ai.opportunity_domain.models" "$TARGET/src/trading_ai/database/models.py"; then
  cat "$ROOT/patches/models_import.txt" >> "$TARGET/src/trading_ai/database/models.py"
fi
cat > "$BACKUP/ROLLBACK.sh" <<EOF
#!/usr/bin/env bash
set -euo pipefail
for path in ${FILES[*]}; do
  if [ -e "$BACKUP/\$path" ]; then
    rm -rf "$TARGET/\$path"
    mkdir -p "$TARGET/\$(dirname "\$path")"
    cp -R "$BACKUP/\$path" "$TARGET/\$path"
  fi
done
EOF
chmod +x "$BACKUP/ROLLBACK.sh"
echo "Applied Milestone 54 Phase 2 to $TARGET"
echo "Backup: $BACKUP"
echo "Next: uv run alembic upgrade head"
