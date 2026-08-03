# Milestone 59 — Institutional Execution Workspace (OMS)

This cumulative package closes the governed workflow gap between Trade Builder and IBKR Paper execution.

## Delivered

- Canonical `execution_intents` domain with immutable audit history.
- Trade Builder handoff from `PAPER_READY` to a database-backed OMS queue.
- Pre-trade validation for paper routing, environment, defined risk, buying power, and leg structure.
- Explicit human approval and exact submission confirmation.
- Reuse of existing IBKR paper binding, routing control, canonical orders, broker orders, reconciliation, and cancellation.
- Broker status synchronization and managed-position creation after a full fill.
- New workstation route: `#/execution-workspace`.
- Queue, risk review, order legs, broker state, actions, and audit timeline.

## Safety

- Paper environment only.
- Live trading remains disabled.
- Existing Milestone 50 routing activation remains authoritative.
- No autonomous submission.
- Direct IBKR submission currently supports one option leg. Multi-leg plans are retained and reviewable, but submission is blocked until atomic IBKR BAG/combo support is enabled. The system will not leg into a spread silently.

## Apply

```bash
./APPLY_MILESTONE59_EXECUTION_WORKSPACE.sh /Users/vinay.hatti/TradingPlatform
cd /Users/vinay.hatti/TradingPlatform
uv run alembic upgrade head
```

## Validate

```bash
cd /Users/vinay.hatti/TradingPlatform
PYTHONPATH=src uv run python scripts/test_m59_execution_workspace.py

cd ui/workstation
npm test
npm run typecheck
npm run build
```

The target Mac should run `npm ci` if native Node dependencies need refreshing before the Vite build.

## Controlled workflow

1. Approve the canonical Opportunity.
2. Build and approve the Trade Plan.
3. Select **Prepare paper intent**.
4. The OMS creates the execution intent and opens `#/execution-workspace`.
5. Validate and approve the intent.
6. Submit using the exact confirmation phrase shown by the UI.
7. Refresh broker status until filled/cancelled/rejected.
8. A fully filled intent creates an idempotent managed position.
