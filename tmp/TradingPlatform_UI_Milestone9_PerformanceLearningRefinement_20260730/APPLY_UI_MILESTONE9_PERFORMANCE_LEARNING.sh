#!/usr/bin/env bash
set -euo pipefail
TARGET="${1:-$(pwd)}"; SRC="$TARGET/ui/workstation/src"; TEST="$TARGET/ui/workstation/tests"
[[ -d "$SRC" ]] || { echo "Missing workstation source: $SRC" >&2; exit 1; }
BACKUP="$TARGET/.ui_milestone9_backup_$(date +%Y%m%d%H%M%S)"; mkdir -p "$BACKUP" "$TEST"
for f in App.tsx PerformanceLearningRefinedPage.tsx performance-learning-refined.css; do [[ -f "$SRC/$f" ]] && cp "$SRC/$f" "$BACKUP/$f"; done
cp "$(dirname "$0")/files/ui/workstation/src/PerformanceLearningRefinedPage.tsx" "$SRC/"
cp "$(dirname "$0")/files/ui/workstation/src/performance-learning-refined.css" "$SRC/"
cp "$(dirname "$0")/files/ui/workstation/tests/ui-milestone9-performance-learning.test.mjs" "$TEST/"
python3 - "$SRC/App.tsx" <<'PY'
from pathlib import Path
import re,sys
p=Path(sys.argv[1]); s=p.read_text()
imp="import { PerformanceLearningRefinedPage } from './PerformanceLearningRefinedPage';"
if imp not in s:
    lines=s.splitlines(); idx=max((i for i,x in enumerate(lines) if x.startswith('import ')),default=-1); lines.insert(idx+1,imp); s='\n'.join(lines)+'\n'
s=re.sub(r"(['\"]performance-learning['\"]\s*:\s*)PerformanceLearningPage",r"\1PerformanceLearningRefinedPage",s)
p.write_text(s)
PY
STATUS="$TARGET/PROJECT_STATUS.md"; if [[ -f "$STATUS" ]] && ! grep -q "UI Milestone 9 — Performance Analytics & Continuous Learning" "$STATUS"; then cat >> "$STATUS" <<'EOF2'

## UI Milestone 9 — Performance Analytics & Continuous Learning
- Status: COMPLETE
- Refined performance attribution, strategy and directional analytics, probability calibration, decision quality, governed recommendations, and learning-policy governance.
- Learning remains human-approved, versioned, evidence-backed, bounded, and non-autonomous.
EOF2
fi
printf '%s\n' "$BACKUP" > "$TARGET/.ui_milestone9_last_backup"
echo "UI Milestone 9 applied. Backup: $BACKUP"
echo "Run npm test, npm run typecheck, and npm run build in ui/workstation."
