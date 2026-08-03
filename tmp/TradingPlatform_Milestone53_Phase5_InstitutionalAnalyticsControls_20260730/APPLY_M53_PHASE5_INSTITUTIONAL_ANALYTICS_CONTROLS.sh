#!/usr/bin/env bash
set -euo pipefail
ROOT="${1:-$(pwd)}"
PKG_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKUP="$ROOT/.rollback/m53_phase5_institutional_analytics_controls_$(date +%Y%m%d_%H%M%S)"
FILES=(
  "src/trading_ai/daily_scan_workstation/models.py"
  "src/trading_ai/daily_scan_workstation/service.py"
  "ui/workstation/src/pages.tsx"
  "ui/workstation/src/types.ts"
  "ui/workstation/src/styles.css"
  "scripts/test_m53_phase5_institutional_analytics_controls.py"
)
mkdir -p "$BACKUP"
for rel in "${FILES[@]}"; do
  if [[ -f "$ROOT/$rel" ]]; then mkdir -p "$BACKUP/$(dirname "$rel")"; cp -p "$ROOT/$rel" "$BACKUP/$rel"; fi
  mkdir -p "$ROOT/$(dirname "$rel")"
  cp -p "$PKG_DIR/$rel" "$ROOT/$rel"
done
printf '%s\n' "$BACKUP" > "$ROOT/.m53_phase5_last_backup"
echo "Applied Milestone 53 Phase 5. Backup: $BACKUP"
