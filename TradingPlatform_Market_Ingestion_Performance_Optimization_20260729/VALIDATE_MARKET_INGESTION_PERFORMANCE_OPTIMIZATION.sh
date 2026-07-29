#!/usr/bin/env bash
set -euo pipefail
TARGET="${1:-/Users/vinay.hatti/TradingPlatform}"
HERE="$(cd "$(dirname "$0")" && pwd)"
cd "$TARGET"

uv run python -m py_compile \
  scripts/run_market_ingestion.py \
  src/trading_ai/trend_intelligence/service.py \
  src/trading_ai/trend_intelligence/transition_service.py \
  src/trading_ai/trend_intelligence/forecast_service.py \
  src/trading_ai/trend_intelligence/institutional_service.py \
  src/trading_ai/trend_intelligence/platform_integration.py \
  src/trading_ai/trend_intelligence/pipeline_service.py

uv run python "$HERE/tests/test_performance_optimization_contract.py"
uv run python "$HERE/tests/test_option_mutable_field_guard.py" "$TARGET"
uv run python scripts/test_trend_intelligence.py
uv run python scripts/test_trend_transition_intelligence.py
uv run python scripts/test_trend_forecasting.py
uv run python scripts/test_trend_platform_integration.py
uv run python scripts/test_trend_market_ingestion_contract.py
uv run python scripts/test_trend_market_ingestion_date_propagation.py

echo "Validation completed successfully."
