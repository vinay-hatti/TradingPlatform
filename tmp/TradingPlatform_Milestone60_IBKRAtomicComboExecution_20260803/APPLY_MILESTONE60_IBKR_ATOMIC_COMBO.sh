#!/usr/bin/env bash
set -euo pipefail
TARGET="${1:-}"
if [[ -z "$TARGET" || ! -d "$TARGET/src/trading_ai" ]]; then
  echo "Usage: $0 /path/to/TradingPlatform" >&2
  exit 2
fi
HERE="$(cd "$(dirname "$0")" && pwd)"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
BACKUP="$TARGET/backups/milestone60_ibkr_atomic_combo_$STAMP"
FILES=(
  src/trading_ai/broker/ibkr/order_models.py
  src/trading_ai/broker/ibkr/order_transport.py
  src/trading_ai/broker/ibkr/order_service.py
  src/trading_ai/execution_workspace/service.py
  ui/workstation/src/ExecutionWorkspacePage.tsx
  scripts/test_m60_ibkr_atomic_combo.py
)
mkdir -p "$BACKUP"
for rel in "${FILES[@]}"; do
  mkdir -p "$BACKUP/$(dirname "$rel")" "$TARGET/$(dirname "$rel")"
  [[ -f "$TARGET/$rel" ]] && cp "$TARGET/$rel" "$BACKUP/$rel"
  cp "$HERE/payload/$rel" "$TARGET/$rel"
done
cat > "$BACKUP/ROLLBACK.sh" <<EOF
#!/usr/bin/env bash
set -euo pipefail
TARGET="${TARGET}"
BACKUP="${BACKUP}"
for rel in ${FILES[*]}; do
  if [[ -f "\$BACKUP/\$rel" ]]; then
    mkdir -p "\$TARGET/\$(dirname \"\$rel\")"
    cp "\$BACKUP/\$rel" "\$TARGET/\$rel"
  else
    rm -f "\$TARGET/\$rel"
  fi
done
echo "Rolled back Milestone 60 from \$BACKUP"
EOF
chmod +x "$BACKUP/ROLLBACK.sh"
STATUS="$TARGET/PROJECT_STATUS.md"
MARKER="## Milestone 60 — Native IBKR Atomic Combo Execution"
if [[ -f "$STATUS" ]] && ! grep -Fq "$MARKER" "$STATUS"; then
cat >> "$STATUS" <<'EOF'

## Milestone 60 — Native IBKR Atomic Combo Execution

**Status:** COMPLETE — 2026-08-03

- Added IBKR `BAG` combo-contract construction for governed multi-leg option intents.
- Resolves each option leg to an IBKR contract ID immediately before submission.
- Submits one atomic paper limit order using governed leg ratios and BUY/SELL actions.
- Preserves exact confirmation, paper-only routing, idempotency, cancellation, synchronization, and managed-position handoff.
- Single-leg option submission remains backward compatible.
- No database migration required.
EOF
fi
echo "Applied Milestone 60 to $TARGET"
echo "Backup: $BACKUP"
echo "No Alembic migration is required."
