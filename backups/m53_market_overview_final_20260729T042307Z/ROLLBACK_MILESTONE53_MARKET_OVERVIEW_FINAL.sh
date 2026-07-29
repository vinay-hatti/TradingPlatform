#!/usr/bin/env bash
set -euo pipefail
BACKUP_DIR="$(cd "$(dirname "$0")" && pwd)"
TARGET="${1:-}"
if [[ -z "$TARGET" || ! -d "$TARGET" ]]; then
  echo "Usage: $0 /path/to/TradingPlatform" >&2
  exit 2
fi
cd "$BACKUP_DIR"
find . -type f ! -name 'ROLLBACK_MILESTONE53_MARKET_OVERVIEW_FINAL.sh' -print0 | while IFS= read -r -d '' file; do
  rel="${file#./}"
  mkdir -p "$TARGET/$(dirname "$rel")"
  cp -p "$file" "$TARGET/$rel"
done
echo "Rolled back final Milestone 53 Market Overview files from $BACKUP_DIR"
