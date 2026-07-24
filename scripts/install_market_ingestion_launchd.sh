#!/usr/bin/env bash
set -euo pipefail
PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
TARGET="$HOME/Library/LaunchAgents/com.tradingplatform.market-ingestion.plist"
mkdir -p "$HOME/Library/LaunchAgents" "$PROJECT_DIR/reports/market_ingestion"
sed "s#__PROJECT_DIR__#$PROJECT_DIR#g" "$PROJECT_DIR/scripts/launchd/com.tradingplatform.market-ingestion.plist.template" > "$TARGET"
launchctl bootout "gui/$(id -u)" "$TARGET" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "$TARGET"
echo "Installed $TARGET (daily at 07:30 and 16:30 local time)."
