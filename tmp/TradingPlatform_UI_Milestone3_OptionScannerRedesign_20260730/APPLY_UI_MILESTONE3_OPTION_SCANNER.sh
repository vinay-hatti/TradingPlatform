#!/usr/bin/env bash
set -euo pipefail
TARGET="${1:-$(pwd)}"
PKG="$(cd "$(dirname "$0")" && pwd)"
UI="$TARGET/ui/workstation"
[ -d "$UI/src" ] || { echo "Workstation source not found: $UI/src" >&2; exit 1; }
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
BACKUP="$TARGET/backups/ui_milestone3_option_scanner_$STAMP"
mkdir -p "$BACKUP/ui/workstation/src" "$BACKUP/ui/workstation/tests"
for f in src/pages.tsx src/styles.css src/OptionScannerWorkspace.tsx tests/option-scanner-redesign.test.mjs; do
  [ -f "$UI/$f" ] && cp "$UI/$f" "$BACKUP/ui/workstation/$f"
done
cp "$PKG/payload/ui/workstation/src/OptionScannerWorkspace.tsx" "$UI/src/OptionScannerWorkspace.tsx"
cp "$PKG/payload/ui/workstation/tests/option-scanner-redesign.test.mjs" "$UI/tests/option-scanner-redesign.test.mjs"
python3 - "$UI/src/pages.tsx" <<'PY'
from pathlib import Path
import re, sys
p=Path(sys.argv[1]); s=p.read_text()
# Preserve previous implementations for rollback/reference while moving both scanner routes to M3.
for name in ('OptionScannerPage','DailyScannerPage'):
    pattern=rf'export function {name}\s*\('
    if re.search(pattern,s) and f'export function Legacy{name}(' not in s:
        s=re.sub(pattern, f'export function Legacy{name}(', s, count=1)
export_line="export { OptionScannerWorkspace as DailyScannerPage, OptionScannerWorkspace as OptionScannerPage } from './OptionScannerWorkspace';"
if export_line not in s:
    imports=list(re.finditer(r"^import .*?;\s*$",s,re.M))
    pos=imports[-1].end() if imports else 0
    s=s[:pos]+"\n"+export_line+s[pos:]
p.write_text(s)
PY
python3 - "$UI/src/styles.css" "$PKG/payload/ui/workstation/src/option-scanner-m3.css" <<'PY'
from pathlib import Path
import sys
p=Path(sys.argv[1]); fragment=Path(sys.argv[2]).read_text(); s=p.read_text()
marker='/* UI Milestone 3 — Institutional Option Scanner */'
if marker not in s: p.write_text(s.rstrip()+"\n\n"+fragment.rstrip()+"\n")
PY
STATUS="$TARGET/PROJECT_STATUS.md"
MARKER='## UI Milestone 3 — Option Scanner Redesign'
if [ -f "$STATUS" ] && ! grep -Fq "$MARKER" "$STATUS"; then
cat >> "$STATUS" <<'MD'

## UI Milestone 3 — Option Scanner Redesign

Status: COMPLETE

- Institutional three-pane Option Scanner workspace
- KPI ribbon, persisted scan controls, saved presets, search, direction filters, favorites
- High-density opportunity grid with score visualization
- Opportunity intelligence drawer and downstream workflow actions
- Persistent diagnostics and responsive layouts
- Existing scanner APIs, ranking logic, provider policy, and database contracts unchanged
MD
fi
cat > "$BACKUP/ROLLBACK.sh" <<ROLLBACK
#!/usr/bin/env bash
set -euo pipefail
TARGET="${TARGET}"
BACKUP="${BACKUP}"
for f in src/pages.tsx src/styles.css src/OptionScannerWorkspace.tsx tests/option-scanner-redesign.test.mjs; do
  if [ -f "\$BACKUP/ui/workstation/\$f" ]; then mkdir -p "\$TARGET/ui/workstation/\$(dirname \$f)"; cp "\$BACKUP/ui/workstation/\$f" "\$TARGET/ui/workstation/\$f"; else rm -f "\$TARGET/ui/workstation/\$f"; fi
done
echo "Rolled back UI Milestone 3."
ROLLBACK
chmod +x "$BACKUP/ROLLBACK.sh"
echo "Applied UI Milestone 3 to $TARGET"
echo "Backup: $BACKUP"
echo "Rollback: $BACKUP/ROLLBACK.sh"
