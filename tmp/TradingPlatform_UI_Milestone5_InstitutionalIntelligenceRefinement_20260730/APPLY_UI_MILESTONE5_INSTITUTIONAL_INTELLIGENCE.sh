#!/usr/bin/env bash
set -euo pipefail
TARGET="${1:-$(pwd)}"; ROOT="$(cd "$(dirname "$0")" && pwd)"; SRC="$TARGET/ui/workstation/src"; BACKUP="$TARGET/.ui_milestone5_backup"
mkdir -p "$SRC" "$TARGET/ui/workstation/tests" "$BACKUP"
for f in InstitutionalIntelligenceRefinedPage.tsx institutional-intelligence-refined.css App.tsx; do [[ -f "$SRC/$f" ]] && cp "$SRC/$f" "$BACKUP/$f" || true; done
cp "$ROOT/files/ui/workstation/src/InstitutionalIntelligenceRefinedPage.tsx" "$SRC/"
cp "$ROOT/files/ui/workstation/src/institutional-intelligence-refined.css" "$SRC/"
cp "$ROOT/files/ui/workstation/tests/ui-milestone5-institutional-intelligence.test.mjs" "$TARGET/ui/workstation/tests/"
APP="$SRC/App.tsx"
python3 - "$APP" <<'PY'
from pathlib import Path
import sys
p=Path(sys.argv[1]); s=p.read_text()
imp="import { InstitutionalIntelligenceRefinedPage } from './InstitutionalIntelligenceRefinedPage';\nimport './institutional-intelligence-refined.css';\n"
if "InstitutionalIntelligenceRefinedPage" not in s:
    lines=s.splitlines(True); idx=0
    while idx<len(lines) and lines[idx].startswith('import '): idx+=1
    lines.insert(idx,imp); s=''.join(lines)
# replace route value while preserving route key
import re
s=re.sub(r"(intelligence\s*:\s*)InstitutionalIntelligencePage",r"\1InstitutionalIntelligenceRefinedPage",s)
s=re.sub(r"(case\s+['\"]intelligence['\"]\s*:\s*return\s*<)InstitutionalIntelligencePage",r"\1InstitutionalIntelligenceRefinedPage",s)
p.write_text(s)
PY
STATUS="$TARGET/PROJECT_STATUS.md"; MARK="UI Milestone 5 — Institutional Intelligence Workspace Refinement"
if [[ -f "$STATUS" ]] && ! grep -q "$MARK" "$STATUS"; then cat >> "$STATUS" <<EOF2

## $MARK
- Refined institutional intelligence workspace installed.
- Existing intelligence REST contracts and versioned snapshots preserved.
- Added evidence hierarchy, category filtering, risk panels, recommendations, playbook, invalidation, and snapshot history.
EOF2
fi
echo "UI Milestone 5 applied. Run npm test, npm run typecheck, and npm run build in ui/workstation."
