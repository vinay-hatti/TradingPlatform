#!/usr/bin/env bash
set -euo pipefail
while IFS= read -r -d '' src; do rel="${src#/Users/vinay.hatti/TradingPlatform/backups/m57_20260730T153052/}"; [ "$rel" = "ROLLBACK.sh" ] && continue; mkdir -p "/Users/vinay.hatti/TradingPlatform/$(dirname "$rel")"; cp -a "$src" "/Users/vinay.hatti/TradingPlatform/$rel"; done < <(find "/Users/vinay.hatti/TradingPlatform/backups/m57_20260730T153052" -type f -print0)
