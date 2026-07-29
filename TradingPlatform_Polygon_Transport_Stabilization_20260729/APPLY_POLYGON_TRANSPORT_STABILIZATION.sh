#!/usr/bin/env bash
set -euo pipefail
PROJECT_ROOT="${1:-$(pwd)}"
PACKAGE_ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$PROJECT_ROOT"
STAMP="$(date +%Y%m%d_%H%M%S)"
BACKUP_DIR="backups/polygon_transport_stabilization_${STAMP}"
mkdir -p "$BACKUP_DIR/src/trading_ai/market/providers" "$BACKUP_DIR/scripts"
for FILE in \
  src/trading_ai/market/service.py \
  src/trading_ai/market/downloader.py \
  src/trading_ai/market/providers/polygon.py \
  scripts/run_market_ingestion.py
do
  if [[ -f "$FILE" ]]; then
    mkdir -p "$BACKUP_DIR/$(dirname "$FILE")"
    cp "$FILE" "$BACKUP_DIR/$FILE"
  fi
done
mkdir -p src/trading_ai/market/providers
cp "$PACKAGE_ROOT/payload/src/trading_ai/market/providers/polygon.py" src/trading_ai/market/providers/polygon.py
cp "$PACKAGE_ROOT/payload/src/trading_ai/market/service.py" src/trading_ai/market/service.py
cp "$PACKAGE_ROOT/payload/src/trading_ai/market/downloader.py" src/trading_ai/market/downloader.py
cp "$PACKAGE_ROOT/payload/scripts/run_market_ingestion.py" scripts/run_market_ingestion.py
uv run python -m compileall -q \
  src/trading_ai/market/providers/polygon.py \
  src/trading_ai/market/service.py \
  src/trading_ai/market/downloader.py \
  scripts/run_market_ingestion.py

echo "Polygon transport stabilization applied."
echo "Backup: $BACKUP_DIR"
