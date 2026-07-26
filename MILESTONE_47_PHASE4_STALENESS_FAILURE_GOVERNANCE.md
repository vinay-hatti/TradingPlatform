# Milestone 47 Phase 4 — Unified Staleness and Failure Governance

Phase 4 makes published-state acceptance and rejection deterministic across the Daily Scanner and Institutional Decision Engine.

## Delivered

- Named consumer policies: `generic`, `scanner`, and `decision`.
- Shared warning-age and maximum-age thresholds.
- Machine-readable failure and warning codes.
- Severity and blocking classifications for every finding.
- Consistent typed exceptions carrying failure codes.
- Required Market Intelligence and option-snapshot timestamp lineage.
- Unified DEGRADED-state handling.
- Scanner and decision consumers now use the same policy factory.

## Failure codes

- `PUBLICATION_MISSING`
- `STATUS_NOT_READY`
- `DEGRADED_NOT_ALLOWED`
- `PUBLICATION_STALE`
- `SCANNER_NOT_READY`
- `DECISION_CONTEXT_NOT_READY`
- `OPTION_SNAPSHOT_MISSING`
- `OPTION_SNAPSHOT_TIMESTAMP_MISSING`
- `MARKET_INTELLIGENCE_TIMESTAMP_MISSING`
- `INVALID_PUBLICATION_RECORD`

A finding is either advisory (`blocking=false`) or rejects the consumer (`blocking=true`). A DEGRADED state remains usable when policy allows it and the relevant readiness flag is true.

## Default thresholds

- Warning age: 24 hours.
- Hard maximum age: 36 hours.
- DEGRADED accepted by default.

Both thresholds remain configurable from the published-state CLI and Daily Scanner command.
