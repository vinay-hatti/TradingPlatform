#!/usr/bin/env bash
set -euo pipefail
TARGET="${1:-}"
BACKUP="${2:-}"
if [[ -z "$TARGET" || -z "$BACKUP" || ! -d "$BACKUP" ]]; then
  echo "Usage: $0 /path/to/TradingPlatform /path/to/backup" >&2
  exit 2
fi
exec "$BACKUP/ROLLBACK.sh"
