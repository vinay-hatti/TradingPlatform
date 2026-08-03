#!/usr/bin/env bash
set -euo pipefail
TARGET="${1:-$(pwd)}"
PACKAGE_DIR="$(cd "$(dirname "$0")" && pwd)"
BACKUP_DIR="$TARGET/.milestone_backups/ui_milestone1_$(date +%Y%m%d_%H%M%S)"
[[ -d "$TARGET/ui/workstation/src" ]] || { echo "ERROR: $TARGET is not a TradingPlatform repository"; exit 1; }
mkdir -p "$BACKUP_DIR/ui/workstation/src" "$BACKUP_DIR/ui/workstation/tests"
for f in App.tsx WorkspaceChrome.tsx styles.css; do
  [[ -f "$TARGET/ui/workstation/src/$f" ]] && cp "$TARGET/ui/workstation/src/$f" "$BACKUP_DIR/ui/workstation/src/$f"
done
[[ -f "$TARGET/ui/workstation/tests/design-system.test.mjs" ]] && cp "$TARGET/ui/workstation/tests/design-system.test.mjs" "$BACKUP_DIR/ui/workstation/tests/"
cp -R "$PACKAGE_DIR/files/." "$TARGET/"
printf '%s\n' "$BACKUP_DIR" > "$TARGET/.ui_milestone1_last_backup"
if [[ -f "$TARGET/PROJECT_STATUS.md" ]] && ! grep -q "UI Milestone 1 — Foundation & Design System" "$TARGET/PROJECT_STATUS.md"; then
cat >> "$TARGET/PROJECT_STATUS.md" <<'STATUS'

## UI Milestone 1 — Foundation & Design System — COMPLETE
- Central semantic design tokens established for color, typography surfaces, spacing, borders, elevation, and responsive layout.
- Institutional application shell introduced with grouped workflow navigation and collapsible sidebar.
- Global Intelligence Header introduced with published context, market/readiness status, paper-governed mode, connection state, global search foundation, and refresh control.
- Shared workspace canvas and diagnostics status bar integrated without changing existing routes or API contracts.
- Design-system contract tests and TypeScript validation added.
STATUS
fi
echo "UI Milestone 1 applied. Backup: $BACKUP_DIR"
echo "Validate: cd $TARGET/ui/workstation && npm test && npm run typecheck && npm run build"
