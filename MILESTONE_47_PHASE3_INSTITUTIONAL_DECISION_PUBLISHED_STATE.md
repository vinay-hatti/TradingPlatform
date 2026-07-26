# Milestone 47 Phase 3 — Institutional Decision Published-State Consumption

The default `InstitutionalDecisionService()` now resolves `current_market_state` before invoking the engine and requires `decision_context_ready=true`.

Every decision run receives report-level lineage in `result.metadata["published_market_state"]`; every decision receives the same immutable publication, ingestion-run, Market Intelligence, and Polygon option-snapshot identifiers.

A `DEGRADED` publication remains usable when the resolver policy permits it and `decision_context_ready` is true. Missing, stale, or decision-unready publications fail before the engine executes.

Compatibility behavior:

- Default production service construction enforces the publication.
- Explicitly injected engines preserve isolated legacy test behavior unless `enforce_published_state=True` is set.
- `allow_unpublished_state=True` is an explicit emergency bypass and is recorded in metadata and warnings.
