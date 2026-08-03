#!/usr/bin/env bash
set -euo pipefail
TARGET="${1:-}"
if [[ -z "$TARGET" || ! -d "$TARGET" ]]; then echo "Usage: $0 /path/to/TradingPlatform" >&2; exit 2; fi
cd "$TARGET"
PYTHONPATH=src uv run python scripts/test_m59_execution_workspace.py
cd ui/workstation
node --test tests/ui-milestone59-execution-workspace.test.mjs
npm test
npm run typecheck
