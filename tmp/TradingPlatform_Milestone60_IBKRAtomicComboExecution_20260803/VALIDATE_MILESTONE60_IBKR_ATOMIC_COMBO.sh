#!/usr/bin/env bash
set -euo pipefail
TARGET="${1:-}"
if [[ -z "$TARGET" || ! -d "$TARGET/src/trading_ai" ]]; then
  echo "Usage: $0 /path/to/TradingPlatform" >&2
  exit 2
fi
cd "$TARGET"
PYTHONPATH=src uv run python scripts/test_m60_ibkr_atomic_combo.py
PYTHONPATH=src uv run python scripts/test_m59_execution_workspace.py
python -m py_compile \
  src/trading_ai/broker/ibkr/order_models.py \
  src/trading_ai/broker/ibkr/order_transport.py \
  src/trading_ai/broker/ibkr/order_service.py \
  src/trading_ai/execution_workspace/service.py
cd ui/workstation
npm test
npm run typecheck
