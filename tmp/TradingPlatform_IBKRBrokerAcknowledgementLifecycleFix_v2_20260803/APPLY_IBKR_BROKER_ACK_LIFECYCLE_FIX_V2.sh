#!/usr/bin/env bash
set -euo pipefail
ROOT="${1:-}"
if [[ -z "$ROOT" || ! -d "$ROOT/src/trading_ai/broker/ibkr" ]]; then echo "Usage: $0 /path/to/TradingPlatform" >&2; exit 2; fi
STAMP=$(date -u +%Y%m%dT%H%M%SZ)
BACKUP="$ROOT/backups/ibkr_broker_ack_lifecycle_fix_v2_$STAMP"
mkdir -p "$BACKUP/src/trading_ai/broker/ibkr"
for f in order_transport.py order_service.py; do cp "$ROOT/src/trading_ai/broker/ibkr/$f" "$BACKUP/src/trading_ai/broker/ibkr/$f"; done
cp "$(dirname "$0")/payload/src/trading_ai/broker/ibkr/order_transport.py" "$ROOT/src/trading_ai/broker/ibkr/order_transport.py"
cp "$(dirname "$0")/payload/src/trading_ai/broker/ibkr/order_service.py" "$ROOT/src/trading_ai/broker/ibkr/order_service.py"
printf '%s\n' "$BACKUP" > "$ROOT/.last_ibkr_ack_fix_v2_backup"
PYTHONPATH="$ROOT/src" "${PYTHON:-python3}" -m py_compile "$ROOT/src/trading_ai/broker/ibkr/order_transport.py" "$ROOT/src/trading_ai/broker/ibkr/order_service.py"
echo "Applied IBKR Broker Acknowledgement Lifecycle Fix v2. Backup: $BACKUP"
