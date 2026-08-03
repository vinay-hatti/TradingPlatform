#!/usr/bin/env bash
set -euo pipefail
TARGET="${1:-$(pwd)}"; ROOT="$(cd "$(dirname "$0")" && pwd)"; SRC="$TARGET/ui/workstation/src"; TESTS="$TARGET/ui/workstation/tests"; BACKUP="$TARGET/.ui_milestone6_backup"
mkdir -p "$SRC" "$TESTS" "$BACKUP"
for f in AdvancedTradeBuilderRefinedPage.tsx advanced-trade-builder-refined.css App.tsx; do [[ -f "$SRC/$f" ]] && cp "$SRC/$f" "$BACKUP/$f" || true; done
cp "$ROOT/files/ui/workstation/src/AdvancedTradeBuilderRefinedPage.tsx" "$SRC/"
cp "$ROOT/files/ui/workstation/src/advanced-trade-builder-refined.css" "$SRC/"
cp "$ROOT/files/ui/workstation/tests/ui-milestone6-advanced-trade-builder.test.mjs" "$TESTS/"
python3 - "$SRC/App.tsx" <<'PY'
from pathlib import Path
import re,sys
p=Path(sys.argv[1]);s=p.read_text();imp="import { AdvancedTradeBuilderRefinedPage } from './AdvancedTradeBuilderRefinedPage';\n"
if "from './AdvancedTradeBuilderRefinedPage'" not in s:
 lines=s.splitlines(True);i=0
 while i<len(lines) and lines[i].startswith('import '):i+=1
 lines.insert(i,imp);s=''.join(lines)
s=re.sub(r"(trade-builder\s*:\s*)AdvancedTradeBuilderPage",r"\1AdvancedTradeBuilderRefinedPage",s)
s=re.sub(r"(case\s+['\"]trade-builder['\"]\s*:\s*return\s*<)AdvancedTradeBuilderPage",r"\1AdvancedTradeBuilderRefinedPage",s)
p.write_text(s)
PY
STATUS="$TARGET/PROJECT_STATUS.md"; MARK="UI Milestone 6 — Advanced Trade Builder Refinement"
if [[ -f "$STATUS" ]] && ! grep -q "$MARK" "$STATUS"; then cat >> "$STATUS" <<EOF2

## $MARK
- Refined governed Trade Builder workspace installed.
- Added payoff preview, capital impact, position sizing, Greeks, validation, lifecycle actions, and plan intelligence.
- Existing TradePlan, execution-intent, and IBKR paper-routing governance preserved.
EOF2
fi
echo "UI Milestone 6 applied. Run npm test, npm run typecheck, and npm run build in ui/workstation."
