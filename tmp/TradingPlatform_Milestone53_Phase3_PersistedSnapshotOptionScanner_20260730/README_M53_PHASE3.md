# Milestone 53 Phase 3 — Persisted-Snapshot Option Scanner

## Purpose

Make Option Scanner a read-only decision workspace that consumes persisted PostgreSQL data only. Daily Scanner remains unchanged and retains its existing ingestion controls.

## Changes

- Removes all market-ingestion, refresh, coverage-threshold, retry, and provider controls from Option Scanner.
- Adds a compact persisted-snapshot status header based on the latest successful `DATA_REFRESH` run.
- Displays snapshot timestamp, age/freshness, publication status, coverage, symbol count, and persisted option-contract count when available.
- Hard-wires Option Scanner scan requests to:
  - `refresh_mode = cache_only`
  - `auto_refresh = false`
  - persisted database-backed option access through the existing `live` option-data contract
- Missing or stale persisted data is surfaced by the backend instead of causing provider calls.
- Preserves Basic, Advanced, and Professional workspace modes.
- Preserves Daily Scanner behavior and operational controls.

## Apply

```bash
cd /Users/vinay.hatti/TradingPlatform

tar -xzf ~/Downloads/TradingPlatform_Milestone53_Phase3_PersistedSnapshotOptionScanner_20260730.tar.gz -C /tmp

/tmp/TradingPlatform_Milestone53_Phase3_PersistedSnapshotOptionScanner_20260730/APPLY_M53_PHASE3_PERSISTED_OPTION_SCANNER.sh \
  /Users/vinay.hatti/TradingPlatform
```

## Validate

```bash
cd /Users/vinay.hatti/TradingPlatform
PYTHONPATH=src uv run python scripts/test_m53_phase3_persisted_snapshot_option_scanner.py
cd ui/workstation
npm run typecheck
npm test
npm run build
```

No database migration is required.
