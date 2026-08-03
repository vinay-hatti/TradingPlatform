#!/usr/bin/env bash
set -euo pipefail
TARGET="${1:-$(pwd)}"
ROOT="$(cd "$(dirname "$0")" && pwd)"
SRC="$ROOT/files/ui/workstation"
DST="$TARGET/ui/workstation"
[ -d "$DST/src" ] || { echo "Missing workstation source: $DST/src" >&2; exit 1; }
BACKUP="$TARGET/.ui_milestone5_type_contract_fix_backup_$(date +%Y%m%d%H%M%S)"
mkdir -p "$BACKUP/src" "$BACKUP/tests"
for f in src/InstitutionalIntelligenceRefinedPage.tsx tests/ui-milestone5-type-contract-fix.test.mjs; do
  if [ -f "$DST/$f" ]; then mkdir -p "$BACKUP/$(dirname "$f")"; cp "$DST/$f" "$BACKUP/$f"; fi
done
cp "$SRC/src/InstitutionalIntelligenceRefinedPage.tsx" "$DST/src/InstitutionalIntelligenceRefinedPage.tsx"
cp "$SRC/tests/ui-milestone5-type-contract-fix.test.mjs" "$DST/tests/ui-milestone5-type-contract-fix.test.mjs"
echo "$BACKUP" > "$TARGET/.ui_milestone5_type_contract_fix_last_backup"
echo "UI Milestone 5 Type Contract Fix applied. Run npm test, npm run typecheck, and npm run build in ui/workstation."
