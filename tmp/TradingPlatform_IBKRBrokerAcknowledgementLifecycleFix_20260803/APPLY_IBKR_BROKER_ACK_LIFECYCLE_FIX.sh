#!/usr/bin/env bash
set -euo pipefail
ROOT="${1:-/Users/vinay.hatti/TradingPlatform}"
python3 "$(cd "$(dirname "$0")" && pwd)/patch_ibkr_ack_lifecycle.py" "$ROOT"
