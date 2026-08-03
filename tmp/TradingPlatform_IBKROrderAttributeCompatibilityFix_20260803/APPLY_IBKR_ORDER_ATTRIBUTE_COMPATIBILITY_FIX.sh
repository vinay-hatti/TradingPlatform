#!/usr/bin/env bash
set -euo pipefail
ROOT="${1:-}"
if [[ -z "$ROOT" || ! -d "$ROOT/src/trading_ai/broker/ibkr" ]]; then
  echo "Usage: $0 /path/to/TradingPlatform" >&2
  exit 2
fi
SRC_DIR="$(cd "$(dirname "$0")" && pwd)/payload/src/trading_ai/broker/ibkr"
TARGET="$ROOT/src/trading_ai/broker/ibkr/order_transport.py"
STAMP="$(date -u +%Y%m%dT%H%M%S)"
BACKUP="$ROOT/backups/ibkr_order_attribute_compatibility_${STAMP}"
mkdir -p "$BACKUP/src/trading_ai/broker/ibkr"
cp "$TARGET" "$BACKUP/src/trading_ai/broker/ibkr/order_transport.py"
cp "$SRC_DIR/order_transport.py" "$TARGET"
printf '%s\n' "$BACKUP" > "$ROOT/.last_ibkr_order_attribute_compatibility_backup"
echo "Applied IBKR order attribute compatibility fix."
echo "Backup: $BACKUP"
