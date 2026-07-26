# Milestone 46.4 — Publication, Recovery and Scanner Readiness

This closure adds an explicit downstream readiness contract to the authoritative ingestion pipeline.

## New governed phases

1. `scanner_readiness` validates required scanner and Market Intelligence tables.
2. `publish_current_snapshot` atomically updates `market_ingestion_publication.current_market_state` only after readiness passes.

The publication row records the ingestion run, Market Intelligence timestamp, Polygon option snapshot identity, readiness state, and complete validation details. Downstream consumers can now resolve one coherent published state rather than independently selecting unrelated latest rows.

## Recovery

Use `scripts/run_m46_ingestion_recovery.py` to recover failed post-ingestion phases without recapturing options. Failures in raw data-capture phases deliberately require a full ingestion rerun.

## Commands

```bash
uv run alembic upgrade head
uv run python scripts/test_m46_4_publication_recovery.py
uv run python scripts/run_m46_scanner_readiness.py --publish
```
