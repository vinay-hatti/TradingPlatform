#!/usr/bin/env bash
set -euo pipefail
ROOT="${1:-$HOME/TradingPlatform}"; INTERVAL="${2:-60}"
PLIST="$HOME/Library/LaunchAgents/com.tradingai.m63-broker-portfolio-sync.plist"
mkdir -p "$(dirname "$PLIST")" "$ROOT/logs"
cat > "$PLIST" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
<key>Label</key><string>com.tradingai.m63-broker-portfolio-sync</string>
<key>ProgramArguments</key><array><string>/bin/zsh</string><string>-lc</string><string>cd "$ROOT" &amp;&amp; uv run python scripts/run_m63_broker_portfolio_sync.py --daemon --interval-seconds "$INTERVAL"</string></array>
<key>RunAtLoad</key><true/><key>KeepAlive</key><true/>
<key>StandardOutPath</key><string>$ROOT/logs/m63_broker_portfolio_sync.log</string>
<key>StandardErrorPath</key><string>$ROOT/logs/m63_broker_portfolio_sync_error.log</string>
</dict></plist>
PLIST
launchctl unload "$PLIST" 2>/dev/null || true
launchctl load "$PLIST"
echo "Installed $PLIST"
