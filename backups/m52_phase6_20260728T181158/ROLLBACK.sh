#!/usr/bin/env bash
set -euo pipefail
TARGET="/Users/vinay.hatti/TradingPlatform"
BACKUP="/Users/vinay.hatti/TradingPlatform/backups/m52_phase6_20260728T181158"
for rel in src/trading_ai/trend_intelligence/operations_contracts.py src/trading_ai/trend_intelligence/operations_policy.py src/trading_ai/trend_intelligence/operations_engine.py src/trading_ai/trend_intelligence/operations_service.py src/trading_ai/trend_intelligence/operations_serialization.py src/trading_ai/trend_intelligence/operations_reporting.py scripts/run_trend_phase6_operations.py scripts/test_m52_phase6_operations.py scripts/test_m52_acceptance.py scripts/test_m52_phase6_package_contract.py MILESTONE_52_CLOSURE.md README_MILESTONE52_PHASE6.md; do
  if [[ -f "$BACKUP/$rel" ]]; then mkdir -p "$TARGET/$(dirname "$rel")"; cp -p "$BACKUP/$rel" "$TARGET/$rel"; else rm -f "$TARGET/$rel"; fi
done
