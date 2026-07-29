#!/usr/bin/env bash
set -euo pipefail
TARGET="${1:-/Users/vinay.hatti/TradingPlatform}"
PKG_DIR="$(cd "$(dirname "$0")" && pwd)"
STAMP="$(date +%Y%m%d_%H%M%S)"
BACKUP="$TARGET/backups/m53_daily_scanner_trend_enrichment_$STAMP"
FILES=(
  src/trading_ai/daily/scanner.py
  src/trading_ai/daily/models.py
  src/trading_ai/daily/trade_candidate.py
  src/trading_ai/daily/recommender.py
  src/trading_ai/daily/reporter.py
  ui/workstation/src/pages.tsx
  scripts/test_m53_daily_scanner_trend_enrichment.py
  scripts/verify_m53_daily_scanner_trend_context.py
)
mkdir -p "$BACKUP"
for rel in "${FILES[@]}"; do
  mkdir -p "$TARGET/$(dirname "$rel")" "$BACKUP/$(dirname "$rel")"
  [[ -f "$TARGET/$rel" ]] && cp -p "$TARGET/$rel" "$BACKUP/$rel"
  cp -p "$PKG_DIR/$rel" "$TARGET/$rel"
done
cat > "$BACKUP/ROLLBACK.sh" <<EOF
#!/usr/bin/env bash
set -euo pipefail
TARGET="${TARGET}"
BACKUP="${BACKUP}"
cd "\$BACKUP"
find . -type f ! -name ROLLBACK.sh -print0 | while IFS= read -r -d '' file; do
  rel="\${file#./}"
  mkdir -p "\$TARGET/\$(dirname "\$rel")"
  cp -p "\$BACKUP/\$rel" "\$TARGET/\$rel"
done
EOF
chmod +x "$BACKUP/ROLLBACK.sh"
echo "Applied Milestone 53 Daily Scanner Trend Enrichment fix."
echo "Backup: $BACKUP"
echo "Rollback: $BACKUP/ROLLBACK.sh"
