#!/usr/bin/env bash
set -euo pipefail
PLIST="$HOME/Library/LaunchAgents/com.tradingai.m63-broker-portfolio-sync.plist"
launchctl unload "$PLIST" 2>/dev/null || true
rm -f "$PLIST"
