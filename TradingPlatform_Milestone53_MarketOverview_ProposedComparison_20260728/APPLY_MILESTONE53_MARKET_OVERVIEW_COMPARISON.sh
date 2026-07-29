#!/usr/bin/env bash
set -euo pipefail
TARGET="${1:-}"
if [[ -z "$TARGET" || ! -d "$TARGET" ]]; then echo "Usage: $0 /path/to/TradingPlatform" >&2; exit 2; fi
SOURCE_DIR="$(cd "$(dirname "$0")" && pwd)"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
BACKUP="$TARGET/backups/m53_market_overview_comparison_$STAMP"
mkdir -p "$BACKUP"
FILES=(
"src/trading_ai/market_overview/contracts.py"
"src/trading_ai/market_overview/service.py"
"src/trading_ai/market_overview/router.py"
"ui/workstation/src/App.tsx"
"ui/workstation/src/types.ts"
"ui/workstation/src/pages.tsx"
"ui/workstation/src/styles.css"
"scripts/test_m53_trend_intelligence_aggregation.py"
"scripts/test_m53_package_contract.py"
"scripts/test_m53_ui_contract.py"
"scripts/test_m53_market_overview_comparison_page.py"
"README_MILESTONE53_MARKET_OVERVIEW_COMPARISON.md"
)
for rel in "${FILES[@]}"; do
  if [[ -f "$TARGET/$rel" ]]; then mkdir -p "$BACKUP/$(dirname "$rel")"; cp -p "$TARGET/$rel" "$BACKUP/$rel"; fi
  mkdir -p "$TARGET/$(dirname "$rel")"; cp -p "$SOURCE_DIR/$rel" "$TARGET/$rel"
done
cat > "$BACKUP/ROLLBACK_MILESTONE53_MARKET_OVERVIEW_COMPARISON.sh" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
BACKUP_DIR="$(cd "$(dirname "$0")" && pwd)"
TARGET="${1:-}"
if [[ -z "$TARGET" || ! -d "$TARGET" ]]; then echo "Usage: $0 /path/to/TradingPlatform" >&2; exit 2; fi
cd "$BACKUP_DIR"
find . -type f ! -name 'ROLLBACK_MILESTONE53_MARKET_OVERVIEW_COMPARISON.sh' -print0 | while IFS= read -r -d '' file; do rel="${file#./}"; mkdir -p "$TARGET/$(dirname "$rel")"; cp -p "$file" "$TARGET/$rel"; done
echo "Rolled back Market Overview comparison package."
EOF
chmod +x "$BACKUP/ROLLBACK_MILESTONE53_MARKET_OVERVIEW_COMPARISON.sh"
echo "Applied proposed Market Overview comparison page to $TARGET"
echo "Current page:  #/market"
echo "Proposed page: #/market-proposed"
echo "Backup: $BACKUP"
