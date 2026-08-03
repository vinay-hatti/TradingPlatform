#!/usr/bin/env bash
set -euo pipefail
TARGET="${1:-}"
if [[ -z "$TARGET" || ! -f "$TARGET/pyproject.toml" ]]; then
  echo "Usage: $0 /path/to/TradingPlatform" >&2
  exit 2
fi
PKG_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
STAMP="$(date +%Y%m%dT%H%M%S)"
BACKUP="$TARGET/backups/platform_launcher_$STAMP"
mkdir -p "$BACKUP/scripts"
for f in start_platform.sh stop_platform.sh platform_status.sh; do
  [[ -f "$TARGET/$f" ]] && cp "$TARGET/$f" "$BACKUP/$f"
done
[[ -f "$TARGET/scripts/platform_launcher.py" ]] && cp "$TARGET/scripts/platform_launcher.py" "$BACKUP/scripts/platform_launcher.py"
mkdir -p "$TARGET/scripts"
cp "$PKG_DIR/payload/scripts/platform_launcher.py" "$TARGET/scripts/platform_launcher.py"
cp "$PKG_DIR/payload/start_platform.sh" "$TARGET/start_platform.sh"
cp "$PKG_DIR/payload/stop_platform.sh" "$TARGET/stop_platform.sh"
cp "$PKG_DIR/payload/platform_status.sh" "$TARGET/platform_status.sh"
chmod +x "$TARGET/start_platform.sh" "$TARGET/stop_platform.sh" "$TARGET/platform_status.sh"
echo "$BACKUP" > "$TARGET/.platform_launcher_last_backup"
echo "Platform Launcher installed. Start with: $TARGET/start_platform.sh"
