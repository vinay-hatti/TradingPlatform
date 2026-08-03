#!/usr/bin/env bash
set -euo pipefail
TARGET="${1:-$(pwd)}"
ROOT="$(cd "$(dirname "$0")" && pwd)"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
BACKUP="$TARGET/backups/m54_phase1_$STAMP"
mkdir -p "$BACKUP"
for p in src/trading_ai/opportunity_domain migrations/versions/m54_001_canonical_opportunity_domain.py scripts/test_m54_phase1_canonical_opportunity_domain.py src/trading_ai/database/models.py; do
  [ -e "$TARGET/$p" ] && { mkdir -p "$BACKUP/$(dirname "$p")"; cp -R "$TARGET/$p" "$BACKUP/$p"; }
done
mkdir -p "$TARGET/src/trading_ai/opportunity_domain" "$TARGET/migrations/versions" "$TARGET/scripts"
cp -R "$ROOT/src/trading_ai/opportunity_domain/." "$TARGET/src/trading_ai/opportunity_domain/"
cp "$ROOT/migrations/versions/m54_001_canonical_opportunity_domain.py" "$TARGET/migrations/versions/"
cp "$ROOT/scripts/test_m54_phase1_canonical_opportunity_domain.py" "$TARGET/scripts/"
if ! grep -q "trading_ai.opportunity_domain.models" "$TARGET/src/trading_ai/database/models.py"; then
  cat "$ROOT/patches/models_import.txt" >> "$TARGET/src/trading_ai/database/models.py"
fi
cat > "$BACKUP/ROLLBACK.sh" <<EOF
#!/usr/bin/env bash
set -euo pipefail
rm -rf "$TARGET/src/trading_ai/opportunity_domain"
rm -f "$TARGET/migrations/versions/m54_001_canonical_opportunity_domain.py" "$TARGET/scripts/test_m54_phase1_canonical_opportunity_domain.py"
if [ -f "$BACKUP/src/trading_ai/database/models.py" ]; then cp "$BACKUP/src/trading_ai/database/models.py" "$TARGET/src/trading_ai/database/models.py"; fi
EOF
chmod +x "$BACKUP/ROLLBACK.sh"
echo "Applied Milestone 54 Phase 1 to $TARGET"
echo "Backup: $BACKUP"
echo "Next: cd $TARGET && uv run alembic upgrade head"
