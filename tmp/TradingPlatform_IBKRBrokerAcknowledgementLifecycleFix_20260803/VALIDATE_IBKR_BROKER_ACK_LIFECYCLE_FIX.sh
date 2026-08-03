#!/usr/bin/env bash
set -euo pipefail
ROOT="${1:-/Users/vinay.hatti/TradingPlatform}"
PYTHONPATH="$ROOT/src" python3 "$(cd "$(dirname "$0")" && pwd)/tests/test_ibkr_broker_ack_lifecycle.py" "$ROOT"
python3 -m py_compile "$ROOT/src/trading_ai/broker/ibkr/order_transport.py" "$ROOT/src/trading_ai/broker/ibkr/order_service.py"
if [ -f "$ROOT/ui/workstation/package.json" ]; then
  (cd "$ROOT/ui/workstation" && npm run typecheck)
fi
