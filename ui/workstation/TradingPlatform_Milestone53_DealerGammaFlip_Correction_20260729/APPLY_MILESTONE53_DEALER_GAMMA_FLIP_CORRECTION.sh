#!/usr/bin/env bash
set -euo pipefail

TARGET="${1:-/Users/vinay.hatti/TradingPlatform}"
PACKAGE_DIR="$(cd "$(dirname "$0")" && pwd)"
STAMP="$(date +%Y%m%d_%H%M%S)"
BACKUP="$TARGET/backups/m53_dealer_gamma_flip_$STAMP"

[[ -d "$TARGET/src/trading_ai" ]] || { echo "Invalid TradingPlatform target: $TARGET" >&2; exit 1; }
mkdir -p "$BACKUP/src/trading_ai/institutional_market_structure" "$BACKUP/ui/workstation/src" "$BACKUP/scripts"

for rel in \
  src/trading_ai/institutional_market_structure/engine.py \
  ui/workstation/src/pages.tsx; do
  if [[ -f "$TARGET/$rel" ]]; then
    mkdir -p "$BACKUP/$(dirname "$rel")"
    cp "$TARGET/$rel" "$BACKUP/$rel"
  fi
done

install -m 0644 "$PACKAGE_DIR/src/trading_ai/institutional_market_structure/engine.py" "$TARGET/src/trading_ai/institutional_market_structure/engine.py"
install -m 0644 "$PACKAGE_DIR/ui/workstation/src/pages.tsx" "$TARGET/ui/workstation/src/pages.tsx"
install -m 0644 "$PACKAGE_DIR/scripts/test_m53_dealer_gamma_flip_correction.py" "$TARGET/scripts/test_m53_dealer_gamma_flip_correction.py"
install -m 0644 "$PACKAGE_DIR/scripts/rebuild_m53_dealer_positioning_gamma_flip.py" "$TARGET/scripts/rebuild_m53_dealer_positioning_gamma_flip.py"

cat > "$BACKUP/ROLLBACK.sh" <<EOF
#!/usr/bin/env bash
set -euo pipefail
TARGET="${TARGET}"
BACKUP="${BACKUP}"
cp "\$BACKUP/src/trading_ai/institutional_market_structure/engine.py" "\$TARGET/src/trading_ai/institutional_market_structure/engine.py"
cp "\$BACKUP/ui/workstation/src/pages.tsx" "\$TARGET/ui/workstation/src/pages.tsx"
echo "Rolled back Milestone 53 dealer gamma-flip correction."
EOF
chmod +x "$BACKUP/ROLLBACK.sh"

echo "Applied Milestone 53 dealer gamma-flip correction."
echo "Backup: $BACKUP"
echo "Rollback: $BACKUP/ROLLBACK.sh"
