# Milestone 48 — Index Price-History Persistence Fix

## Root cause

The index branch created `MarketService(provider=index_provider)` and passed it to
`MarketDownloader`. That custom service had no database session/repository wiring, so the
command could download/cache index bars and report success without writing `price_history`.

## Correction

The index branch now uses `IndexHistoryIngestionService`, which:

- fetches Polygon `I:SPX`, `I:NDX`, and `I:RUT` aggregates;
- validates canonical `SPX`, `NDX`, and `RUT` bars;
- normalizes Polygon millisecond timestamps to UTC dates;
- upserts `trading_ai.market.models.PriceHistory` through SQLAlchemy ORM;
- commits once per symbol and rolls back on failure;
- verifies the persisted row count before reporting success;
- reports downloaded, inserted, updated, and persisted counts separately;
- preserves the existing equity/ETF ingestion path unchanged.

No Alembic migration is required.
