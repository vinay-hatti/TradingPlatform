#!/usr/bin/env bash
set -euo pipefail
TARGET="/Users/vinay.hatti/TradingPlatform"
BACKUP="/Users/vinay.hatti/TradingPlatform/backups/m53_daily_scanner_trend_freshness_20260729_000630"
cd "$BACKUP"
find . -type f ! -name ROLLBACK.sh -print0 | while IFS= read -r -d '' file; do
  rel="${file#./}"
  mkdir -p "$TARGET/$(dirname "$rel")"
  cp -p "$BACKUP/$rel" "$TARGET/$rel"
done
