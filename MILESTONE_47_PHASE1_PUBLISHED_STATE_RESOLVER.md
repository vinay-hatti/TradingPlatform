# Milestone 47 Phase 1 — Published Market State Resolver

This phase introduces the permanent consumer boundary for `current_market_state`.
Scanner and decision services should resolve this state before reading timestamped
analytics and must not independently select unrelated latest records.

## Capabilities

- Typed publication context and lineage
- READY/DEGRADED policy enforcement
- Scanner and decision readiness gates
- Configurable publication staleness
- Required option snapshot lineage
- Explicit unavailable, stale and not-ready errors
- Stable CLI and JSON operational report

## Validation

```bash
uv run python scripts/test_m47_phase1_published_state_resolver.py
uv run python scripts/run_published_market_state.py --consumer scanner
uv run python scripts/run_published_market_state.py --consumer decision
```

A DEGRADED publication remains usable when the corresponding readiness flag is
true and policy permits degraded state. No fallback to un-published latest rows
is performed.
