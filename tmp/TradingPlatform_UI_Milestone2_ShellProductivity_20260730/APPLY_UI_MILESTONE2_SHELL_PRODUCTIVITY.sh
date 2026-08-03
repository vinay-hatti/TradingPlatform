#!/usr/bin/env bash
set -euo pipefail
TARGET="${1:-$(pwd)}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PAYLOAD="$SCRIPT_DIR/payload"
BACKUP="$TARGET/.ui_milestone2_backup"

[[ -d "$TARGET/ui/workstation/src" ]] || { echo "ERROR: TradingPlatform workstation not found at $TARGET" >&2; exit 1; }
if [[ ! -d "$BACKUP" ]]; then
  mkdir -p "$BACKUP/ui/workstation/src" "$BACKUP/ui/workstation/tests"
  for file in App.tsx WorkspaceChrome.tsx WorkspaceProductivity.tsx styles.css; do
    [[ -f "$TARGET/ui/workstation/src/$file" ]] && cp "$TARGET/ui/workstation/src/$file" "$BACKUP/ui/workstation/src/$file"
  done
  for file in design-system.test.mjs workspace-productivity.test.mjs; do
    [[ -f "$TARGET/ui/workstation/tests/$file" ]] && cp "$TARGET/ui/workstation/tests/$file" "$BACKUP/ui/workstation/tests/$file"
  done
fi
cp -R "$PAYLOAD/ui/workstation/src/." "$TARGET/ui/workstation/src/"
mkdir -p "$TARGET/ui/workstation/tests"
cp -R "$PAYLOAD/ui/workstation/tests/." "$TARGET/ui/workstation/tests/"

STATUS="$TARGET/PROJECT_STATUS.md"
MARKER="UI Modernization Milestone 2 — Shell Productivity"
if [[ -f "$STATUS" ]] && ! grep -Fq "$MARKER" "$STATUS"; then
  printf '\n\n' >> "$STATUS"
  cat "$SCRIPT_DIR/PROJECT_STATUS_UI_MILESTONE2.md" >> "$STATUS"
fi

echo "UI Milestone 2 applied successfully to $TARGET"
echo "Run: cd $TARGET/ui/workstation && npm test && npm run typecheck && npm run build"
