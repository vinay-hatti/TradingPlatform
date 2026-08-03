#!/usr/bin/env bash
set -euo pipefail
for path in src/trading_ai/opportunity_domain src/trading_ai/production_api/app.py ui/workstation/src/App.tsx ui/workstation/src/api.ts ui/workstation/src/pages.tsx ui/workstation/src/styles.css ui/workstation/src/types.ts migrations/versions/m54_001_canonical_opportunity_domain.py scripts/test_m54_phase2_institutional_opportunity_workspace.py src/trading_ai/database/models.py; do
  if [ -e "/Users/vinay.hatti/TradingPlatform/backups/m54_phase2_20260730T185815Z/$path" ]; then
    rm -rf "/Users/vinay.hatti/TradingPlatform/$path"
    mkdir -p "/Users/vinay.hatti/TradingPlatform/$(dirname "$path")"
    cp -R "/Users/vinay.hatti/TradingPlatform/backups/m54_phase2_20260730T185815Z/$path" "/Users/vinay.hatti/TradingPlatform/$path"
  fi
done
