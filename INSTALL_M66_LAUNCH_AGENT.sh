#!/usr/bin/env bash
set -euo pipefail
TARGET="${1:-/Users/vinay.hatti/TradingPlatform}"; INTERVAL="${2:-300}"
PLIST="$HOME/Library/LaunchAgents/com.tradingai.m66.production-operations.plist"
mkdir -p "$(dirname "$PLIST")" "$TARGET/logs"
cat > "$PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
<key>Label</key><string>com.tradingai.m66.production-operations</string>
<key>ProgramArguments</key><array><string>/bin/zsh</string><string>-lc</string><string>cd '$TARGET' &amp;&amp; uv run python scripts/run_m66_production_operations.py --daemon --interval-seconds $INTERVAL</string></array>
<key>RunAtLoad</key><true/><key>KeepAlive</key><true/>
<key>StandardOutPath</key><string>$TARGET/logs/m66_production_operations.log</string>
<key>StandardErrorPath</key><string>$TARGET/logs/m66_production_operations_error.log</string>
</dict></plist>
EOF
launchctl bootout gui/$(id -u) "$PLIST" 2>/dev/null || true
launchctl bootstrap gui/$(id -u) "$PLIST"
echo "Installed $PLIST (safe simulation mode)."
