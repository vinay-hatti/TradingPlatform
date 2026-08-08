#!/usr/bin/env bash
set -euo pipefail
PLIST="$HOME/Library/LaunchAgents/com.tradingplatform.m65-performance-learning.plist"; launchctl unload "$PLIST" 2>/dev/null || true; rm -f "$PLIST"; echo 'Removed Milestone 65 launch agent.'
