# Milestone 69.6 — Governed Event Intelligence Automation

## Bound source policy

- Alpha Vantage: corporate earnings (`EARNINGS_CALENDAR`, `horizon=6month`)
- Federal Reserve: FOMC meeting calendar
- BLS: CPI, PPI, Employment Situation, JOLTS
- BEA: GDP and Personal Income and Outlays (PCE / Personal Income components)
- Polygon: underlying and option-derived move evidence (persisted into registry fields)

## Daily operation

```bash
uv run alembic upgrade head
uv run python scripts/sync_m69_event_calendar.py --horizon-months 6
uv run python scripts/compute_m69_event_expected_moves.py
uv run python scripts/verify_m69_event_calendar.py
```

Synchronization is idempotent. `calendar_source + source_event_key` is unique. A canonical content hash prevents writes for unchanged records. Revisions update the existing row and increment `revision_number`.

The Alpha Vantage key is read only from `ALPHAVANTAGE_API_KEY`.

## Ingestion integration

Options finalization now runs `event_expected_moves` after contract optimization and before M69 option valuation. Calendar synchronization remains a separate daily task so source outages do not erase the last verified calendar or block option ingestion.

## Operational statuses

- READY: source records normalized and no structural integrity failures
- DEGRADED: calendar remains usable but expected-move components are incomplete
- FAILED: duplicate source keys, missing dates, or an unrecoverable execution error
