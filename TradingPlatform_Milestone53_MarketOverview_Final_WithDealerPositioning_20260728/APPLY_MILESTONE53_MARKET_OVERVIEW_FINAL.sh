#!/usr/bin/env bash
set -euo pipefail
TARGET="${1:-}"
if [[ -z "$TARGET" || ! -d "$TARGET" ]]; then
  echo "Usage: $0 /path/to/TradingPlatform" >&2
  exit 2
fi
SOURCE_DIR="$(cd "$(dirname "$0")" && pwd)"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
BACKUP="$TARGET/backups/m53_market_overview_final_$STAMP"
mkdir -p "$BACKUP"
FILES=(
  "ui/workstation/src/App.tsx"
  "ui/workstation/src/pages.tsx"
  "ui/workstation/src/styles.css"
  "ui/workstation/src/types.ts"
  "scripts/test_m53_market_overview_final_page.py"
  "scripts/test_m53_ui_contract.py"
  "README_MILESTONE53_MARKET_OVERVIEW_FINAL.md"
)
for rel in "${FILES[@]}"; do
  if [[ -f "$TARGET/$rel" ]]; then
    mkdir -p "$BACKUP/$(dirname "$rel")"
    cp -p "$TARGET/$rel" "$BACKUP/$rel"
  fi
  mkdir -p "$TARGET/$(dirname "$rel")"
  cp -p "$SOURCE_DIR/$rel" "$TARGET/$rel"
done
cat > "$BACKUP/ROLLBACK_MILESTONE53_MARKET_OVERVIEW_FINAL.sh" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
BACKUP_DIR="$(cd "$(dirname "$0")" && pwd)"
TARGET="${1:-}"
if [[ -z "$TARGET" || ! -d "$TARGET" ]]; then
  echo "Usage: $0 /path/to/TradingPlatform" >&2
  exit 2
fi
cd "$BACKUP_DIR"
find . -type f ! -name 'ROLLBACK_MILESTONE53_MARKET_OVERVIEW_FINAL.sh' -print0 | while IFS= read -r -d '' file; do
  rel="${file#./}"
  mkdir -p "$TARGET/$(dirname "$rel")"
  cp -p "$file" "$TARGET/$rel"
done
echo "Rolled back final Milestone 53 Market Overview files from $BACKUP_DIR"
EOF
chmod +x "$BACKUP/ROLLBACK_MILESTONE53_MARKET_OVERVIEW_FINAL.sh"
echo "Applied final Milestone 53 Market Overview to $TARGET"
echo "Backup: $BACKUP"
