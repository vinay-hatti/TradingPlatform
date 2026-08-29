#!/bin/bash
set -euo pipefail
PROJECT_DIR="${1:-/Users/vinay.hatti/TradingPlatform}"
INTERVAL="${2:-5}"
LABEL="com.tradingplatform.m73.entry-fill-management"
PLIST="$HOME/Library/LaunchAgents/${LABEL}.plist"
LOG_DIR="$PROJECT_DIR/logs/m73"
mkdir -p "$HOME/Library/LaunchAgents" "$LOG_DIR"
cat > "$PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
<key>Label</key><string>${LABEL}</string>
<key>ProgramArguments</key><array><string>/bin/zsh</string><string>-lc</string><string>cd '${PROJECT_DIR}' &amp;&amp; uv run python scripts/run_m73_entry_fill_management.py --portfolio-id PAPER-PRIMARY</string></array>
<key>StartInterval</key><integer>${INTERVAL}</integer>
<key>RunAtLoad</key><true/>
<key>StandardOutPath</key><string>${LOG_DIR}/entry_fill.out.log</string>
<key>StandardErrorPath</key><string>${LOG_DIR}/entry_fill.err.log</string>
<key>ProcessType</key><string>Background</string>
</dict></plist>
EOF
launchctl bootout "gui/$(id -u)/${LABEL}" >/dev/null 2>&1 || true
launchctl bootstrap "gui/$(id -u)" "$PLIST"
echo "Installed ${LABEL} at ${INTERVAL}s interval"
echo "Log: ${LOG_DIR}/entry_fill.out.log"
