# Milestone 54 Phase 2 — Institutional Opportunity Workspace

This cumulative package adds the canonical Opportunity REST API and workstation UI on top of the Phase 1 domain model.

## Capabilities

- Canonical staging from Option Scanner into PostgreSQL
- Opportunity inbox with search, state filtering, and sorting
- Evidence and provenance review
- Governed lifecycle transitions with optimistic version checks
- Append-only audit timeline
- Responsive workstation navigation and layout
- No market ingestion or provider calls

## Apply

```bash
bash APPLY_M54_PHASE2_INSTITUTIONAL_OPPORTUNITY_WORKSPACE.sh /Users/vinay.hatti/TradingPlatform
cd /Users/vinay.hatti/TradingPlatform
uv run alembic upgrade head
```

## Validate

```bash
PYTHONPATH=src uv run python scripts/test_m54_phase2_institutional_opportunity_workspace.py
cd ui/workstation
npm run typecheck
npm test
npm run build
```

Open `#/opportunities` after starting the workstation.
