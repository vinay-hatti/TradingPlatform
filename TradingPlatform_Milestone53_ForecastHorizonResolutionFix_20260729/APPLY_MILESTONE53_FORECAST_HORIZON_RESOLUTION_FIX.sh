#!/usr/bin/env bash
set -euo pipefail
TARGET="${1:-/Users/vinay.hatti/TradingPlatform}"
SOURCE_DIR="$(cd "$(dirname "$0")" && pwd)"
STAMP="$(date +%Y%m%dT%H%M%S)"
BACKUP="$TARGET/backups/m53_forecast_horizon_resolution_$STAMP"
FILE="src/trading_ai/trend_intelligence/forecast_repository.py"
mkdir -p "$BACKUP/$(dirname "$FILE")" "$TARGET/$(dirname "$FILE")" "$TARGET/scripts"
if [[ -f "$TARGET/$FILE" ]]; then cp "$TARGET/$FILE" "$BACKUP/$FILE"; fi
cp "$SOURCE_DIR/$FILE" "$TARGET/$FILE"
cp "$SOURCE_DIR/scripts/test_m53_forecast_horizon_resolution_fix.py" "$TARGET/scripts/"
echo "Applied Milestone 53 Forecast Horizon Resolution Fix to $TARGET"
echo "Backup: $BACKUP"
