# Milestone 47 Phase 5 — Persistent Scanner and Decision Lineage

Phase 5 adds relational, immutable ancestry from the published market state through scanner runs, scanner candidates, institutional decision runs, and individual decisions.

## Tables

- `scanner_lineage_run`
- `scanner_candidate_lineage`
- `institutional_decision_lineage_run`
- `institutional_decision_lineage`

The tables retain publication, ingestion-run, Market Intelligence, Polygon option-snapshot, version, status, hash, timestamps, and serialized payload fields. Existing analytics and reporting tables are unchanged.

## Runtime integration

`run_daily_scan.py` creates a scanner run ID, persists the scanner run and every candidate, then propagates `scanner_run_id`, `candidate_id`, `market_state_hash`, and `scanner_version` to live-trade candidates and report metadata.

The default governed `InstitutionalDecisionService` creates a decision run ID and persists the run and each decision. Explicitly injected legacy test engines remain non-persistent unless `persist_lineage=True` is selected.

## Migration

Apply `m47_001` after `m46_003`.
