#!/usr/bin/env bash
set -euo pipefail
TARGET="/Users/vinay.hatti/TradingPlatform"
BACKUP="/Users/vinay.hatti/TradingPlatform/backups/milestone60_ibkr_atomic_combo_20260803T171448Z"
for rel in src/trading_ai/broker/ibkr/order_models.py src/trading_ai/broker/ibkr/order_transport.py src/trading_ai/broker/ibkr/order_service.py src/trading_ai/execution_workspace/service.py ui/workstation/src/ExecutionWorkspacePage.tsx scripts/test_m60_ibkr_atomic_combo.py; do
  if [[ -f "$BACKUP/$rel" ]]; then
    mkdir -p "$TARGET/$(dirname \"$rel\")"
    cp "$BACKUP/$rel" "$TARGET/$rel"
  else
    rm -f "$TARGET/$rel"
  fi
done
echo "Rolled back Milestone 60 from $BACKUP"
