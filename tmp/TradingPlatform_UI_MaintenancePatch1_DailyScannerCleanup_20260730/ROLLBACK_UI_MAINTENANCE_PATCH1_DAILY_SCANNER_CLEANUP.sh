#!/usr/bin/env bash
set -euo pipefail
ROOT="${1:-/Users/vinay.hatti/TradingPlatform}"
POINTER="$ROOT/.ui_patch_backups/latest_daily_scanner_cleanup_backup.txt"
BACKUP="${2:-}"
if [[ -z "$BACKUP" ]]; then
  [[ -f "$POINTER" ]] || { echo "Backup pointer not found: $POINTER" >&2; exit 1; }
  BACKUP="$(cat "$POINTER")"
fi
[[ -f "$BACKUP/manifest.json" ]] || { echo "Invalid backup: $BACKUP" >&2; exit 1; }
python3 - "$ROOT" "$BACKUP" <<'PY'
import json, shutil, sys
from pathlib import Path
root=Path(sys.argv[1]); backup=Path(sys.argv[2])
for item in json.loads((backup/'manifest.json').read_text()):
    rel=Path(item['file']); src=backup/rel; dst=root/rel
    dst.parent.mkdir(parents=True,exist_ok=True); shutil.copy2(src,dst)
    print('restored',rel)
PY
rm -f "$ROOT/ui/workstation/tests/daily-scanner-workflow-cleanup.test.mjs"
echo "Rollback completed from $BACKUP"
