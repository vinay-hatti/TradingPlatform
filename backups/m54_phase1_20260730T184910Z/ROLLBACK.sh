#!/usr/bin/env bash
set -euo pipefail
rm -rf "/Users/vinay.hatti/TradingPlatform/src/trading_ai/opportunity_domain"
rm -f "/Users/vinay.hatti/TradingPlatform/migrations/versions/m54_001_canonical_opportunity_domain.py" "/Users/vinay.hatti/TradingPlatform/scripts/test_m54_phase1_canonical_opportunity_domain.py"
if [ -f "/Users/vinay.hatti/TradingPlatform/backups/m54_phase1_20260730T184910Z/src/trading_ai/database/models.py" ]; then cp "/Users/vinay.hatti/TradingPlatform/backups/m54_phase1_20260730T184910Z/src/trading_ai/database/models.py" "/Users/vinay.hatti/TradingPlatform/src/trading_ai/database/models.py"; fi
