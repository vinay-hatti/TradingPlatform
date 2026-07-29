#!/usr/bin/env bash
set -euo pipefail
TARGET="${1:-/Users/vinay.hatti/TradingPlatform}"
ROOT="$(cd "$(dirname "$0")" && pwd)"
for f in \
  src/trading_ai/trend_intelligence/forecast_repository.py \
  src/trading_ai/daily/models.py \
  src/trading_ai/daily/trade_candidate.py \
  src/trading_ai/daily/recommender.py \
  src/trading_ai/daily/reporter.py \
  src/trading_ai/daily/scanner.py \
  scripts/test_m53_forecast_horizon_candidate_propagation.py; do
  mkdir -p "$TARGET/$(dirname "$f")"
  cp "$ROOT/$f" "$TARGET/$f"
done
printf 'Applied Milestone 53 forecast horizon candidate propagation fix to %s\n' "$TARGET"
