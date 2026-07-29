#!/usr/bin/env bash
set -euo pipefail
TARGET="${1:-/Users/vinay.hatti/TradingPlatform}"
PACKAGE_DIR="$(cd "$(dirname "$0")" && pwd)"
STAMP="$(date +%Y%m%d_%H%M%S)"
BACKUP="$TARGET/backups/m53_index_trend_intelligence_$STAMP"
mkdir -p "$BACKUP"
FILES=(
  src/trading_ai/trend_intelligence/service.py
  src/trading_ai/trend_intelligence/institutional_service.py
  scripts/run_institutional_trend_intelligence.py
  scripts/rebuild_m53_index_trend_intelligence.py
  scripts/test_m53_index_trend_intelligence_correction.py
)
for rel in "${FILES[@]}"; do
  if [[ -f "$TARGET/$rel" ]]; then mkdir -p "$BACKUP/$(dirname "$rel")"; cp "$TARGET/$rel" "$BACKUP/$rel"; fi
  mkdir -p "$TARGET/$(dirname "$rel")"
  cp "$PACKAGE_DIR/$rel" "$TARGET/$rel"
done
cat > "$BACKUP/ROLLBACK.sh" <<EOF
#!/usr/bin/env bash
set -euo pipefail
cp -R "$BACKUP/src" "$TARGET/" 2>/dev/null || true
cp -R "$BACKUP/scripts" "$TARGET/" 2>/dev/null || true
EOF
chmod +x "$BACKUP/ROLLBACK.sh"
echo "Applied Milestone 53 index trend intelligence correction."
echo "Backup: $BACKUP"
