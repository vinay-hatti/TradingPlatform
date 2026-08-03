#!/usr/bin/env bash
set -euo pipefail
ROOT="${1:-}"
if [[ -z "$ROOT" ]]; then echo "Usage: $0 /path/to/TradingPlatform" >&2; exit 2; fi
uv run python "$(cd "$(dirname "$0")" && pwd)/tests/test_ibkr_order_attribute_compatibility.py" "$ROOT"
PY
cat > "$PKG/README.md" <<'MD'
# IBKR Order Attribute Compatibility Fix

For installed `ibapi 9.81.1-1`, `Order()` defaults `eTradeOnly=True` and `firmQuoteOnly=True`. Modern TWS/Gateway rejects these fields with errors 10268/10269. This package explicitly sets both to `False` for single-leg and BAG combo orders. `nbboPriceCap` remains unchanged at IBKR's unset sentinel.

No database migration is required.
MD
chmod +x "$PKG"/*.sh
uv run python "$PKG/tests/test_ibkr_order_attribute_compatibility.py" "$PKG/payload/../../.." >/dev/null 2>&1 || true
# Validate directly on payload via temp root structure
TMP=$(mktemp -d)
mkdir -p "$TMP/src/trading_ai/broker/ibkr"
cp "$PKG/payload/src/trading_ai/broker/ibkr/order_transport.py" "$TMP/src/trading_ai/broker/ibkr/"
uv run python "$PKG/tests/test_ibkr_order_attribute_compatibility.py" "$TMP"
rm -rf "$TMP"
cd /mnt/data
tar -czf TradingPlatform_IBKROrderAttributeCompatibilityFix_20260803.tar.gz TradingPlatform_IBKROrderAttributeCompatibilityFix_20260803
shasum -a 256 TradingPlatform_IBKROrderAttributeCompatibilityFix_20260803.tar.gz > TradingPlatform_IBKROrderAttributeCompatibilityFix_20260803.tar.gz.sha256
ls -lh TradingPlatform_IBKROrderAttributeCompatibilityFix_20260803.tar.gz*
