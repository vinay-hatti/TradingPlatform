#!/usr/bin/env bash
set -euo pipefail
TARGET="${1:-$(pwd)}"; SRC="$(cd "$(dirname "$0")" && pwd)/payload"; TS="$TARGET/ui/workstation/src/pages.tsx"; BACKUP="$TARGET/.milestone_backups/ui_m4_$(date +%Y%m%d_%H%M%S)"
[[ -f "$TS" ]] || { echo "Missing $TS" >&2; exit 1; }; mkdir -p "$BACKUP/ui/workstation/src" "$BACKUP/ui/workstation/tests"
cp "$TS" "$BACKUP/ui/workstation/src/pages.tsx"; for f in OpportunityWorkspaceM4.tsx opportunity-workspace-m4.css; do [[ -f "$TARGET/ui/workstation/src/$f" ]]&&cp "$TARGET/ui/workstation/src/$f" "$BACKUP/ui/workstation/src/$f"||true; done
cp "$SRC/ui/workstation/src/OpportunityWorkspaceM4.tsx" "$TARGET/ui/workstation/src/"; cp "$SRC/ui/workstation/src/opportunity-workspace-m4.css" "$TARGET/ui/workstation/src/"; cp "$SRC/ui/workstation/tests/opportunity-workspace-refinement.test.mjs" "$TARGET/ui/workstation/tests/"
python3 - "$TS" <<'PY'
from pathlib import Path
import re,sys
p=Path(sys.argv[1]); s=p.read_text()
if "from './OpportunityWorkspaceM4'" not in s:
 s=re.sub(r'export function OpportunityWorkspacePage\(\)', 'function LegacyOpportunityWorkspacePage()', s, count=1)
 s += "\nexport { OpportunityWorkspacePage } from './OpportunityWorkspaceM4';\n"
p.write_text(s)
PY
printf '%s\n' "$BACKUP" > "$TARGET/.ui_m4_last_backup"
STATUS="$TARGET/PROJECT_STATUS.md"; touch "$STATUS"; grep -q "UI Milestone 4 — Institutional Opportunity Workspace Refinement" "$STATUS" || cat >> "$STATUS" <<'STATUS'

## UI Milestone 4 — Institutional Opportunity Workspace Refinement — COMPLETE
- Three-pane canonical opportunity review workspace
- Review queues, evidence scores, favorites, comparison selection, analyst notes, lifecycle actions, audit timeline, and downstream workflow handoffs
- Existing opportunity APIs and optimistic version governance preserved
STATUS
echo "UI Milestone 4 applied. Backup: $BACKUP"
