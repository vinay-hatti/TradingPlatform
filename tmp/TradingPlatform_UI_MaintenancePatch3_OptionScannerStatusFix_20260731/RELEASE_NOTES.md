# Release Notes

## Fixed

The Option Scanner previously searched `/api/v1/scanner/runs` for a successful `DATA_REFRESH` and displayed `No published snapshot found` when none was returned. This was misleading because the Option Scanner is powered by successful persisted `DAILY_SCAN` results.

## New compact status

The Scanner workspace now shows:

- persisted scanner-data readiness;
- latest successful scan timestamp;
- freshness derived from available scan lineage;
- coverage and symbol count when reported;
- options-data status when reported;
- the read-only/no-ingestion policy.

Missing optional metadata is labeled `Not reported`, not `UNKNOWN` or missing snapshot.
