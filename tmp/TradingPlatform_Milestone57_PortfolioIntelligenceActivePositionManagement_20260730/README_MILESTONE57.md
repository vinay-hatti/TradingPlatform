# Milestone 57 — Portfolio Intelligence & Active Position Management

This cumulative milestone extends Milestone 56 with a canonical managed-position lifecycle, portfolio/position intelligence, health history, governed position actions, attribution, immutable portfolio snapshots, REST APIs, and the Portfolio Intelligence workstation.

## Capabilities

- Verified lineage: Opportunity → Intelligence → Trade Plan → Managed Position
- Position states: OPEN, PARTIAL, HEDGED, ROLLED, CLOSED, CANCELLED
- Governed actions: HOLD, SCALE_IN, SCALE_OUT, ROLL, HEDGE, CLOSE
- Optimistic version checks and append-only events
- Health scoring, drift alerts, decision recommendations
- Portfolio Greeks, exposure, concentration, risk, valuation snapshots
- Post-trade attribution foundation
- Paper-only integration boundary; no silent broker submission

## Apply

```bash
./APPLY_MILESTONE57_PORTFOLIO_INTELLIGENCE.sh /Users/vinay.hatti/TradingPlatform
cd /Users/vinay.hatti/TradingPlatform
uv run alembic upgrade head
PYTHONPATH=src uv run python scripts/test_m57_portfolio_intelligence.py
cd ui/workstation && npm run typecheck && npm test && npm run build
```

Open `#/portfolio` in the workstation.

## New API

- `GET /api/v1/portfolio-intelligence/positions`
- `POST /api/v1/portfolio-intelligence/positions/from-trade-plan`
- `POST /api/v1/portfolio-intelligence/positions/{id}/marks`
- `POST /api/v1/portfolio-intelligence/positions/{id}/actions`
- `GET /api/v1/portfolio-intelligence/positions/{id}/events`
- `GET /api/v1/portfolio-intelligence/positions/{id}/health`
- `POST /api/v1/portfolio-intelligence/positions/{id}/attribution`
- `POST /api/v1/portfolio-intelligence/portfolios/{portfolio_id}/snapshots`
- `GET /api/v1/portfolio-intelligence/portfolios/{portfolio_id}/snapshot`
