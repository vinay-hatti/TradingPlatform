# Milestone 47 Phase 2 — Daily Scanner Published-State Consumption

The daily scanner now resolves `current_market_state` before scanning, enforces scanner readiness and staleness policy, and propagates immutable publication lineage into every candidate, live trade, CSV, JSON, and HTML report metadata.

Normal scans reject missing, stale, non-ready, or unreferenced option states. `--allow-unpublished-state` exists only as an emergency compatibility override. `--require-ready-published-state` rejects DEGRADED publications.
