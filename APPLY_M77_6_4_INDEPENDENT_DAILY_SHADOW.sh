#!/bin/bash
set -euo pipefail

TARGET="${1:-/Users/vinay.hatti/TradingPlatform}"
PKG_DIR="$(cd "$(dirname "$0")" && pwd)"
STAMP="$(date +%Y%m%d_%H%M%S)"
BACKUP="$TARGET/backups/m77_6_4_independent_daily_shadow_${STAMP}"
LAUNCH_PLIST="$HOME/Library/LaunchAgents/com.tradingplatform.m77-6-shadow.plist"

if [ ! -d "$TARGET" ] || [ ! -f "$TARGET/pyproject.toml" ]; then
  echo "ERROR: target does not look like TradingPlatform: $TARGET" >&2
  exit 2
fi

if [ ! -f "$TARGET/scripts/run_m77_6_live_forward_shadow.py" ]; then
  echo "ERROR: M77.6 runtime is not installed." >&2
  exit 3
fi

mkdir -p \
  "$BACKUP/scripts/m77_6_shadow" \
  "$BACKUP/launchd" \
  "$TARGET/scripts/m77_6_shadow" \
  "$TARGET/tests/m77_6_4" \
  "$TARGET/logs/m77_6_shadow" \
  "$HOME/Library/LaunchAgents"

if [ -f "$TARGET/scripts/m77_6_shadow/run_daily_shadow_collector.sh" ]; then
  cp "$TARGET/scripts/m77_6_shadow/run_daily_shadow_collector.sh" \
     "$BACKUP/scripts/m77_6_shadow/"
fi
if [ -f "$LAUNCH_PLIST" ]; then
  cp "$LAUNCH_PLIST" "$BACKUP/launchd/"
fi

cp "$PKG_DIR/scripts/m77_6_shadow/run_daily_shadow_collector.sh" \
   "$TARGET/scripts/m77_6_shadow/run_daily_shadow_collector.sh"
chmod +x "$TARGET/scripts/m77_6_shadow/run_daily_shadow_collector.sh"

cp "$PKG_DIR/tests/m77_6_4/test_m77_6_4_independent_daily_shadow.py" \
   "$TARGET/tests/m77_6_4/test_m77_6_4_independent_daily_shadow.py"

cp "$PKG_DIR/launchd/com.tradingplatform.m77-6-shadow.plist" \
   "$LAUNCH_PLIST"

echo "Applied M77.6.4 Independent Daily Shadow Collector"
echo "Backup: $BACKUP"
echo "Production ingestion changes: NONE"
echo "Production intelligence/decision/execution changes: NONE"
echo "Alembic: NONE"
echo "Schedule: weekdays 18:30 local time"
echo
echo "Running strict verification..."

cd "$TARGET"

CURRENT="$(uv run alembic current 2>&1)"
echo "$CURRENT"
if ! echo "$CURRENT" | grep -q "m77_003"; then
  echo "ERROR: M77.6.4 requires m77_003 current." >&2
  exit 4
fi

uv run python "$PKG_DIR/VERIFY_M77_6_4_SOURCE.py"

# Focused package tests need the plist copy available under the project for static test.
mkdir -p "$TARGET/launchd"
cp "$PKG_DIR/launchd/com.tradingplatform.m77-6-shadow.plist" \
   "$TARGET/launchd/com.tradingplatform.m77-6-shadow.plist"
uv run python -m pytest -q tests/m77_6_4

echo
echo "Installing/reloading LaunchAgent..."
launchctl bootout "gui/$(id -u)/com.tradingplatform.m77-6-shadow" >/dev/null 2>&1 || true
launchctl bootstrap "gui/$(id -u)" "$LAUNCH_PLIST"

echo
echo "=== LAUNCHAGENT STATUS ==="
launchctl print "gui/$(id -u)/com.tradingplatform.m77-6-shadow" | \
  egrep 'state =|path =|program =|last exit code =|runs =|pid =' || true

echo
echo "Installation verified."
echo "Manual acceptance run:"
echo "  launchctl kickstart -k gui/$(id -u)/com.tradingplatform.m77-6-shadow"
echo "  tail -100 logs/m77_6_shadow/launchd.out.log"
echo "  tail -100 logs/m77_6_shadow/launchd.err.log"
