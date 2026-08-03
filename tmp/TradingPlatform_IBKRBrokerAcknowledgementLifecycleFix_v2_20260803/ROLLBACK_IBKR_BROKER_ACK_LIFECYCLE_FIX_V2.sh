#!/usr/bin/env bash
set -euo pipefail
ROOT="${1:-}"
MARKER="$ROOT/.last_ibkr_ack_fix_v2_backup"
[[ -f "$MARKER" ]] || { echo "Backup marker not found: $MARKER" >&2; exit 2; }
BACKUP=$(cat "$MARKER")
for f in order_transport.py order_service.py; do cp "$BACKUP/src/trading_ai/broker/ibkr/$f" "$ROOT/src/trading_ai/broker/ibkr/$f"; done
echo "Rolled back from $BACKUP"
