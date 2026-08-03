#!/usr/bin/env bash
set -euo pipefail
ROOT="${1:-}"
PYTHONPATH="$ROOT/src" uv run python "$(dirname "$0")/tests/test_ibkr_ack_fix_v2.py" "$ROOT"
PYTHONPATH="$ROOT/src" uv run python -m py_compile "$ROOT/src/trading_ai/broker/ibkr/order_transport.py" "$ROOT/src/trading_ai/broker/ibkr/order_service.py"
echo "IBKR Broker Acknowledgement Lifecycle Fix v2 validation passed."
