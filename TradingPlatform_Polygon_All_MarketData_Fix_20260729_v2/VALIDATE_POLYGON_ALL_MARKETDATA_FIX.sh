#!/usr/bin/env bash
set -euo pipefail
PROJECT_ROOT="${1:-$(pwd)}"
cd "$PROJECT_ROOT"
uv run python scripts/run_market_ingestion.py --data-scope underlying --symbols AAPL,MSFT,SPY --lookback-days 30 --force-underlying-refresh --max-workers 1 --request-interval 1 --continue-on-error
cat <<'SQL'

Validate in PostgreSQL:
SELECT symbol, MAX(date) AS latest_date, COUNT(*) AS rows
FROM price_history
WHERE symbol IN ('AAPL','MSFT','SPY')
GROUP BY symbol
ORDER BY symbol;
SQL
