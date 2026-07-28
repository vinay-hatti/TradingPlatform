cd /Users/vinay.hatti/TradingPlatform

echo
echo "================================================================"
echo "MILESTONE 50 — INSTALLED FILES"
echo "================================================================"

find src scripts tests alembic/versions \
  -type f \
  \( -iname '*m50*' \
     -o -iname '*ibkr*' \
     -o -iname '*paper_order*' \
     -o -iname '*order_routing*' \) \
  -print \
  | sort

echo
echo "================================================================"
echo "MILESTONE 50 — ACTIVATION REFERENCES"
echo "================================================================"

grep -RniE \
  "READY_FOR_EXPLICIT_ACTIVATION|paper_order_submission_enabled|PAPER_ORDER_ROUTING_DISABLED|activate|activation|smoke.test|submit.*order|cancel.*order" \
  src scripts tests \
  --include='*.py' \
  2>/dev/null \
  | head -n 400

echo
echo "================================================================"
echo "MILESTONE 50 — AVAILABLE COMMANDS"
echo "================================================================"

uv run python -m trading_ai --help 2>&1 \
  | grep -iE \
  "ibkr|paper|order|routing|broker|execution" \
  || true

echo
echo "================================================================"
echo "MILESTONE 50 — VALIDATION SCRIPT"
echo "================================================================"

sed -n '1,320p' \
  scripts/validate_m50_ibkr_paper_order_routing.py

echo
echo "================================================================"
echo "MILESTONE 50 — ROUTING TEST CONTRACT"
echo "================================================================"

sed -n '1,420p' \
  tests/milestone50/test_m50_ibkr_paper_order_routing.py
