# Milestone 45 — Market Overview

Database-backed top-down analytics for the Trading Operations Workstation.

## Flow

`price_history` + latest `dealer_position_snapshot` → `MarketOverviewService` → timestamped overview/breadth/sector snapshots → API → Market Overview UI → Daily Scanner market-context adjustment.

## Install

```bash
uv run alembic upgrade head
uv run python scripts/run_m45_market_overview.py
cd ui/workstation && npm install && npm run build
```

## API

- `GET /api/v1/market-overview/latest`
- `POST /api/v1/market-overview/refresh`
- `GET /api/v1/market-overview/scanner-context`

## Governance

All analytics consume persisted PostgreSQL data. Dealer positioning remains explicitly model-derived from OI and Greeks. Intraday history is preserved with `snapshot_timestamp`.
