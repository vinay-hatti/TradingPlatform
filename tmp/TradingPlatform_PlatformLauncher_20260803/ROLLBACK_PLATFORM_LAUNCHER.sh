#!/usr/bin/env bash
set -euo pipefail
TARGET="${1:-}"
if [[ -z "$TARGET" || ! -d "$TARGET" ]]; then
  echo "Usage: $0 /path/to/TradingPlatform" >&2
  exit 2
fi
MARKER="$TARGET/.platform_launcher_last_backup"
if [[ ! -f "$MARKER" ]]; then
  echo "No Platform Launcher backup marker found." >&2
  exit 1
fi
BACKUP="$(cat "$MARKER")"
for f in start_platform.sh stop_platform.sh platform_status.sh; do
  if [[ -f "$BACKUP/$f" ]]; then cp "$BACKUP/$f" "$TARGET/$f"; else rm -f "$TARGET/$f"; fi
done
if [[ -f "$BACKUP/scripts/platform_launcher.py" ]]; then
  cp "$BACKUP/scripts/platform_launcher.py" "$TARGET/scripts/platform_launcher.py"
else
  rm -f "$TARGET/scripts/platform_launcher.py"
fi
rm -f "$MARKER"
echo "Platform Launcher rolled back from $BACKUP"
