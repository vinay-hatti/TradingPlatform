#!/usr/bin/env bash
set -euo pipefail
TARGET="/Users/vinay.hatti/TradingPlatform"
BACKUP="/Users/vinay.hatti/TradingPlatform/backups/m53_dealer_gamma_flip_20260729_005338"
cp "$BACKUP/src/trading_ai/institutional_market_structure/engine.py" "$TARGET/src/trading_ai/institutional_market_structure/engine.py"
cp "$BACKUP/ui/workstation/src/pages.tsx" "$TARGET/ui/workstation/src/pages.tsx"
echo "Rolled back Milestone 53 dealer gamma-flip correction."
