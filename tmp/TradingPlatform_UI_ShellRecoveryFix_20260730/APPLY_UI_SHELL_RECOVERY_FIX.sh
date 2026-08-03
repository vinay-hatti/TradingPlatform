#!/usr/bin/env bash
set -euo pipefail
TARGET="${1:-$(pwd)}"
SRC="$(cd "$(dirname "$0")" && pwd)/payload"
APP="$TARGET/ui/workstation/src/App.tsx"
STYLES="$TARGET/ui/workstation/src/styles.css"
[[ -f "$APP" && -f "$STYLES" ]] || { echo "Missing workstation App.tsx or styles.css under $TARGET" >&2; exit 1; }
BACKUP="$TARGET/.milestone_backups/ui_shell_recovery_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BACKUP/ui/workstation/src" "$BACKUP/ui/workstation/tests"
cp "$APP" "$BACKUP/ui/workstation/src/App.tsx"
cp "$STYLES" "$BACKUP/ui/workstation/src/styles.css"
for f in WorkstationRouteBoundary.tsx workstation-shell-recovery.css; do
  [[ -f "$TARGET/ui/workstation/src/$f" ]] && cp "$TARGET/ui/workstation/src/$f" "$BACKUP/ui/workstation/src/$f" || true
done
cp "$SRC/ui/workstation/src/WorkstationRouteBoundary.tsx" "$TARGET/ui/workstation/src/"
cp "$SRC/ui/workstation/src/workstation-shell-recovery.css" "$TARGET/ui/workstation/src/"
cp "$SRC/ui/workstation/tests/workstation-shell-recovery.test.mjs" "$TARGET/ui/workstation/tests/"
python3 - "$APP" <<'PY'
from pathlib import Path
import re, sys
p=Path(sys.argv[1]); s=p.read_text()
if "./WorkstationRouteBoundary" not in s:
    imports=list(re.finditer(r"^import .*?;\s*$", s, flags=re.M))
    if not imports: raise SystemExit("Unable to locate App.tsx import block")
    pos=imports[-1].end()
    s=s[:pos]+"\nimport { WorkstationRouteBoundary } from './WorkstationRouteBoundary';\nimport './workstation-shell-recovery.css';"+s[pos:]
# Wrap the active route, supporting the current modernization App shape.
old='<WorkspaceCanvas><div className="content" key={`${active}-${refreshToken}`}><Page/></div></WorkspaceCanvas>'
new='<WorkspaceCanvas><div className="content" key={`${active}-${refreshToken}`}><WorkstationRouteBoundary routeKey={active}><Page/></WorkstationRouteBoundary></div></WorkspaceCanvas>'
if old in s:
    s=s.replace(old,new,1)
elif '<WorkstationRouteBoundary routeKey={active}><Page/></WorkstationRouteBoundary>' not in s:
    s2,n=re.subn(r'<Page\s*/>', r'<WorkstationRouteBoundary routeKey={active}><Page/></WorkstationRouteBoundary>', s, count=1)
    if n!=1: raise SystemExit("Unable to patch active route boundary")
    s=s2
p.write_text(s)
PY
printf '%s\n' "$BACKUP" > "$TARGET/.ui_shell_recovery_last_backup"
echo "UI shell recovery fix applied. Backup: $BACKUP"
