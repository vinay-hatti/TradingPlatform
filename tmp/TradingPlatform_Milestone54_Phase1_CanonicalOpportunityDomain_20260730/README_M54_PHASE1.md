# Milestone 54 Phase 1 — Canonical Opportunity Domain

Adds PostgreSQL-backed canonical opportunities, immutable scanner/snapshot provenance, governed workflow states, optimistic version checks, idempotent staging, and append-only audit events.

## Apply

```bash
./APPLY_M54_PHASE1_CANONICAL_OPPORTUNITY_DOMAIN.sh /Users/vinay.hatti/TradingPlatform
cd /Users/vinay.hatti/TradingPlatform
uv run alembic upgrade head
PYTHONPATH=src uv run python scripts/test_m54_phase1_canonical_opportunity_domain.py
```

## Tables

- `opportunities`
- `opportunity_audit_events`

No UI route is added in Phase 1. Phase 2 will build the Opportunity Workspace against this canonical repository.
