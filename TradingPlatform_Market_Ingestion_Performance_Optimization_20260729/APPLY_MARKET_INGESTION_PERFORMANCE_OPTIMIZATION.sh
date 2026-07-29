#!/usr/bin/env bash
set -euo pipefail
TARGET="${1:-/Users/vinay.hatti/TradingPlatform}"
HERE="$(cd "$(dirname "$0")" && pwd)"
STAMP="$(date +%Y%m%dT%H%M%S)"
BACKUP="$TARGET/backups/market_ingestion_performance_optimization_$STAMP"

[[ -d "$TARGET/src/trading_ai" ]] || { echo "Invalid TradingPlatform target: $TARGET" >&2; exit 1; }
uv run python "$HERE/tests/test_option_mutable_field_guard.py" "$TARGET"
mkdir -p "$BACKUP/scripts" "$BACKUP/src/trading_ai/trend_intelligence"
cp "$TARGET/scripts/run_market_ingestion.py" "$BACKUP/scripts/"
for f in service.py transition_service.py forecast_service.py institutional_service.py platform_integration.py __init__.py; do
  cp "$TARGET/src/trading_ai/trend_intelligence/$f" "$BACKUP/src/trading_ai/trend_intelligence/"
done
[[ -f "$TARGET/src/trading_ai/trend_intelligence/pipeline_service.py" ]] && cp "$TARGET/src/trading_ai/trend_intelligence/pipeline_service.py" "$BACKUP/src/trading_ai/trend_intelligence/"

cp "$HERE/payload/scripts/run_market_ingestion.py" "$TARGET/scripts/"
cp "$HERE/payload/src/trading_ai/trend_intelligence/"*.py "$TARGET/src/trading_ai/trend_intelligence/"
chmod +x "$TARGET/scripts/run_market_ingestion.py"

echo "Applied Market Ingestion Performance Optimization to $TARGET"
echo "Backup: $BACKUP"
