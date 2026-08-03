#!/usr/bin/env bash
set -euo pipefail
TARGET="${1:-$(pwd)}"
PACKAGE_DIR="$(cd "$(dirname "$0")" && pwd)"
BACKUP="$TARGET/.m54_phase3_backup_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BACKUP"
FILES=(
  src/trading_ai/opportunity_domain/__init__.py
  src/trading_ai/opportunity_domain/models.py
  src/trading_ai/opportunity_domain/policy.py
  src/trading_ai/opportunity_domain/profile.py
  src/trading_ai/opportunity_domain/repository.py
  src/trading_ai/opportunity_domain/service.py
  src/trading_ai/opportunity_domain/router.py
  src/trading_ai/production_api/app.py
  migrations/versions/m54_001_canonical_opportunity_domain.py
  ui/workstation/src/pages.tsx
  ui/workstation/src/api.ts
  ui/workstation/src/App.tsx
  ui/workstation/src/styles.css
  ui/workstation/src/types.ts
  scripts/test_m54_phase3_opportunity_comparison.py
)
for file in "${FILES[@]}"; do
  if [[ -f "$TARGET/$file" ]]; then mkdir -p "$BACKUP/$(dirname "$file")"; cp "$TARGET/$file" "$BACKUP/$file"; fi
  mkdir -p "$TARGET/$(dirname "$file")"; cp "$PACKAGE_DIR/$file" "$TARGET/$file"
done
echo "$BACKUP" > "$TARGET/.m54_phase3_last_backup"
echo "Applied Milestone 54 Phase 3 to $TARGET"
echo "Backup: $BACKUP"
