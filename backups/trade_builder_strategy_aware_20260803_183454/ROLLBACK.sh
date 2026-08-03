#!/usr/bin/env bash
set -euo pipefail
cp "/Users/vinay.hatti/TradingPlatform/backups/trade_builder_strategy_aware_20260803_183454/ui/workstation/src/AdvancedTradeBuilderPage.tsx" "/Users/vinay.hatti/TradingPlatform/ui/workstation/src/AdvancedTradeBuilderPage.tsx"
rm -rf "/Users/vinay.hatti/TradingPlatform/ui/workstation/dist"
if [ -d "/Users/vinay.hatti/TradingPlatform/backups/trade_builder_strategy_aware_20260803_183454/dist" ]; then cp -R "/Users/vinay.hatti/TradingPlatform/backups/trade_builder_strategy_aware_20260803_183454/dist" "/Users/vinay.hatti/TradingPlatform/ui/workstation/dist"; fi
echo "Rollback complete."
