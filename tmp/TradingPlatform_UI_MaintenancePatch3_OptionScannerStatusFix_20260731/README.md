# UI Maintenance Patch 3 — Option Scanner Persisted-Data Status Fix

This patch corrects the Option Scanner status display introduced by UI Maintenance Patch 2.

## Changes

- Stops treating `DATA_REFRESH` run history as the only evidence of persisted scanner readiness.
- Resolves status from the latest successful `DAILY_SCAN` and its result metadata.
- Removes the misleading **No published snapshot found** message.
- Uses **Not reported** when optional coverage metadata is absent.
- Merges persisted-data readiness into a compact strip inside **Scanner workspace**.
- Removes the separate five-column snapshot row.
- Preserves cache-only scanning, scan payloads, saved workspaces, filters, results, and handoff behavior.

The installer expects UI Maintenance Patch 2 as its baseline and creates a timestamped backup.
