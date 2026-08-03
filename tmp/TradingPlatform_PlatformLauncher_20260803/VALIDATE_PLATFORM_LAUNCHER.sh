#!/usr/bin/env bash
set -euo pipefail
TARGET="${1:-}"
if [[ -z "$TARGET" || ! -f "$TARGET/scripts/platform_launcher.py" ]]; then
  echo "Usage: $0 /path/to/TradingPlatform" >&2
  exit 2
fi
cd "$TARGET"
uv run python -m py_compile scripts/platform_launcher.py
uv run python "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/tests/test_platform_launcher.py"
bash -n start_platform.sh stop_platform.sh platform_status.sh
echo "Platform Launcher validation passed."
