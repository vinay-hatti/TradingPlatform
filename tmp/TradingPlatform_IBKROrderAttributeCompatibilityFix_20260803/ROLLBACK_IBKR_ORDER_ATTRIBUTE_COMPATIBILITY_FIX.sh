#!/usr/bin/env bash
set -euo pipefail
ROOT="${1:-}"
if [[ -z "$ROOT" ]]; then echo "Usage: $0 /path/to/TradingPlatform" >&2; exit 2; fi
MARKER="$ROOT/.last_ibkr_order_attribute_compatibility_backup"
[[ -f "$MARKER" ]] || { echo "No backup marker found: $MARKER" >&2; exit 1; }
BACKUP="$(cat "$MARKER")"
cp "$BACKUP/src/trading_ai/broker/ibkr/order_transport.py" "$ROOT/src/trading_ai/broker/ibkr/order_transport.py"
echo "Rolled back from $BACKUP"
