#!/usr/bin/env bash
set -euo pipefail
LABEL="com.tradingplatform.m69-6-event-intelligence"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
rm -f "$PLIST"
echo "Uninstalled $LABEL"
