#!/usr/bin/env bash
set -euo pipefail
TARGET="${1:-$(pwd)}"
MARKER="$TARGET/.ui_milestone5_type_contract_fix_last_backup"
[ -f "$MARKER" ] || { echo "No backup marker found." >&2; exit 1; }
BACKUP="$(cat "$MARKER")"
DST="$TARGET/ui/workstation"
if [ -f "$BACKUP/src/InstitutionalIntelligenceRefinedPage.tsx" ]; then cp "$BACKUP/src/InstitutionalIntelligenceRefinedPage.tsx" "$DST/src/InstitutionalIntelligenceRefinedPage.tsx"; fi
if [ -f "$BACKUP/tests/ui-milestone5-type-contract-fix.test.mjs" ]; then cp "$BACKUP/tests/ui-milestone5-type-contract-fix.test.mjs" "$DST/tests/ui-milestone5-type-contract-fix.test.mjs"; else rm -f "$DST/tests/ui-milestone5-type-contract-fix.test.mjs"; fi
rm -f "$MARKER"
echo "UI Milestone 5 Type Contract Fix rolled back."
