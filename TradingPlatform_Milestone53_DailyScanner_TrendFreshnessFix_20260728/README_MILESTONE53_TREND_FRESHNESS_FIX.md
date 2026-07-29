# Milestone 53 — Trend Snapshot Freshness Fix

This cumulative package includes the Daily Scanner forecast/institutional enrichment and corrects freshness governance.

## Corrections

- Snapshot age is measured in business days rather than calendar days.
- Latest snapshot selection orders by `as_of_date DESC, snapshot_timestamp DESC`.
- Queries honor the scanner/reference date and do not select future snapshots.
- STALE responses now include the selected snapshot date.

A Friday 2026-07-24 snapshot evaluated on Tuesday 2026-07-28 is two business days old, not four calendar days old.
