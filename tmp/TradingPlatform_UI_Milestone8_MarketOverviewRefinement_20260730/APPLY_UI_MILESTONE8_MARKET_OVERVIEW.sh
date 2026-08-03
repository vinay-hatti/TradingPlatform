#!/usr/bin/env bash
set -euo pipefail
TARGET="${1:-$(pwd)}"; SRC="$TARGET/ui/workstation/src"; TEST="$TARGET/ui/workstation/tests"
[[ -d "$SRC" ]] || { echo "Missing workstation source: $SRC" >&2; exit 1; }
BACKUP="$TARGET/.ui_milestone8_backup_$(date +%Y%m%d%H%M%S)"; mkdir -p "$BACKUP" "$TEST"
for f in App.tsx MarketOverviewRefinedPage.tsx market-overview-refined.css; do [[ -f "$SRC/$f" ]] && cp "$SRC/$f" "$BACKUP/$f"; done
cp "$(dirname "$0")/files/ui/workstation/src/MarketOverviewRefinedPage.tsx" "$SRC/"
cp "$(dirname "$0")/files/ui/workstation/src/market-overview-refined.css" "$SRC/"
cp "$(dirname "$0")/files/ui/workstation/tests/ui-milestone8-market-overview.test.mjs" "$TEST/"
python3 - "$SRC/App.tsx" <<'PY'
from pathlib import Path
import re,sys
p=Path(sys.argv[1]);s=p.read_text();imp="import { MarketOverviewRefinedPage } from './MarketOverviewRefinedPage';"
if imp not in s:
 lines=s.splitlines();i=max(i for i,x in enumerate(lines) if x.startswith('import '));lines.insert(i+1,imp);s='\n'.join(lines)+'\n'
s=re.sub(r'(^\s*market:\s*)[^,]+,',r'\1MarketOverviewRefinedPage,',s,flags=re.M);p.write_text(s)
PY
STATUS="$TARGET/PROJECT_STATUS.md"; if [[ -f "$STATUS" ]] && ! grep -q "UI Milestone 8 — Market Overview Command Center" "$STATUS"; then cat >> "$STATUS" <<'EOF2'

## UI Milestone 8 — Market Overview Command Center
- Status: COMPLETE
- Refined breadth, regime, institutional participation, volatility, liquidity, sector rotation, cross-asset, dealer-positioning, risk, and freshness views.
- Market ingestion remains the authoritative central data driver; the page consumes persisted Market Overview snapshots only.
EOF2
fi
printf '%s\n' "$BACKUP" > "$TARGET/.ui_milestone8_last_backup"
echo "UI Milestone 8 applied. Backup: $BACKUP"
echo "Run npm test, npm run typecheck, and npm run build in ui/workstation."
