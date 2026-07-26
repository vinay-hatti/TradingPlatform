# Milestone 46.3 — Persistence and Type Governance

## Purpose

This hardening release fixes Market Intelligence persistence failures caused by NumPy and pandas values crossing the SQL/JSON boundary without conversion.

## Root cause fixed

A `numpy.float64` confidence value reached psycopg2 and was rendered as `np.float64(...)`, which PostgreSQL interpreted as a schema-qualified expression (`schema "np" does not exist`).

## Changes

- Added `trading_ai.persistence_normalization` as the canonical persistence-boundary converter.
- Converts NumPy floats, integers, booleans, datetime values, arrays, pandas timestamps, `NaN`, infinity, and `pandas.NA` into native Python or `NULL` values.
- Uses strict JSON serialization with `allow_nan=False`.
- Normalizes the complete Market Intelligence snapshot before every persistence operation.
- Normalizes volatility and liquidity analytics before SQL/JSON persistence.
- Adds `REUSED` and `NO_NEW_DATA` successful ingestion statuses.
- Reports actual OHLCV row counts and distinguishes idempotent zero-row runs.
- Adds a targeted Market Intelligence refresh script so an earlier failed final phase can be recovered without recapturing options.

## Recovery

After installing this package, run:

```bash
uv run python scripts/run_m46_market_intelligence_refresh.py
```

Then verify:

```sql
SELECT snapshot_timestamp, as_of_date, overall_sentiment_score,
       sentiment_label, confidence
FROM market_sentiment_snapshot
ORDER BY snapshot_timestamp DESC
LIMIT 5;
```

## Validation

```bash
uv run python scripts/test_m46_3_persistence_type_governance.py
uv run python scripts/test_m46_2_authoritative_provider_policy.py
uv run python scripts/test_m46_2_unified_market_ingestion.py
uv run python scripts/test_m46_polygon_closure.py
uv run python scripts/test_m46_migration_governance.py
uv run python scripts/test_m46_market_intelligence.py
uv run python scripts/test_m46_integration_contracts.py
```
