#!/usr/bin/env bash
set -euo pipefail
TARGET="${1:-/Users/vinay.hatti/TradingPlatform}"; INTERVAL="${2:-3600}"; LABEL="com.tradingplatform.m65-performance-learning"; PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
mkdir -p "$HOME/Library/LaunchAgents" "$TARGET/logs"
cat > "$PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?><!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd"><plist version="1.0"><dict><key>Label</key><string>$LABEL</string><key>ProgramArguments</key><array><string>/bin/zsh</string><string>-lc</string><string>cd '$TARGET' &amp;&amp; uv run python scripts/run_m65_performance_learning.py</string></array><key>StartInterval</key><integer>$INTERVAL</integer><key>RunAtLoad</key><true/><key>StandardOutPath</key><string>$TARGET/logs/m65_performance_learning.log</string><key>StandardErrorPath</key><string>$TARGET/logs/m65_performance_learning_error.log</string></dict></plist>
EOF
launchctl unload "$PLIST" 2>/dev/null || true; launchctl load "$PLIST"; echo "Installed $LABEL ($INTERVAL seconds)"
