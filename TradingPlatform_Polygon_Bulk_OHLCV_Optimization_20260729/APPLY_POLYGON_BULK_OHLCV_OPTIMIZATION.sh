#!/usr/bin/env bash
set -euo pipefail
TARGET="${1:-/Users/vinay.hatti/TradingPlatform}"
ROOT="$(cd "$(dirname "$0")" && pwd)"
STAMP="$(date +%Y%m%dT%H%M%S)"
BACKUP="$TARGET/backups/polygon_bulk_ohlcv_optimization_$STAMP"
FILES=(
  "src/trading_ai/market/service.py"
  "src/trading_ai/market/downloader.py"
  "src/trading_ai/market/providers/polygon.py"
  "scripts/run_market_ingestion.py"
)
mkdir -p "$BACKUP"
for rel in "${FILES[@]}"; do
  mkdir -p "$BACKUP/$(dirname "$rel")" "$TARGET/$(dirname "$rel")"
  if [[ -f "$TARGET/$rel" ]]; then cp "$TARGET/$rel" "$BACKUP/$rel"; fi
  cp "$ROOT/payload/$rel" "$TARGET/$rel"
done
chmod +x "$TARGET/scripts/run_market_ingestion.py" 2>/dev/null || true
cd "$TARGET"
uv run python -m py_compile "${FILES[@]}"
echo "Applied Polygon bulk OHLCV optimization to $TARGET"
echo "Backup: $BACKUP"
