# Milestone 49 — Authoritative Paper Trading Data Model

Milestone 49 establishes PostgreSQL as the operational source of truth for paper trading while preserving the existing order-management, paper-execution, paper-position, portfolio, and risk domain contracts.

## Included

- Database-backed canonical order repository with optimistic concurrency.
- Canonical order-event persistence.
- Database-backed paper executions and fills.
- Authoritative paper positions through `portfolio_positions`.
- Cash reservations for pending paper orders.
- Transactional fill accounting across execution, cash ledger, reservation, position, and lifecycle event.
- Database-backed paper runtime sessions, automation checkpoints, and trading controls.
- Position marks and lifecycle-event tables.
- Account summary and reconciliation service.
- Idempotent execution settlement.
- Migration `m49_001`.
- Milestone validation script and regression tests.

## Governance

- Paper trading only.
- No live-broker connector or live-order route is introduced.
- JSON repositories remain backward-compatible test/report adapters, but PostgreSQL is authoritative for new operational integration.
- `portfolio_positions` remains the authoritative position table.
- `portfolio_cash_ledger` remains the authoritative cash ledger.

## Installation

From the repository root:

```bash
uv run alembic upgrade head
uv run pytest -q tests/milestone49/test_m49_authoritative_persistence.py
uv run python scripts/run_m49_authoritative_paper_trading_validation.py --account-id PAPER-PRIMARY
```

Create the primary paper account once, from Python or a future Milestone 50 workflow:

```python
from trading_ai.authoritative_paper_trading import AuthoritativePaperAccountService

service = AuthoritativePaperAccountService()
service.create_account(
    account_id="PAPER-PRIMARY",
    name="Primary Paper Account",
    initial_capital=100_000.0,
)
```

## New tables

- `canonical_orders`
- `canonical_order_events`
- `paper_executions`
- `paper_fills`
- `portfolio_cash_reservations`
- `paper_trading_sessions`
- `paper_automation_checkpoints`
- `paper_trading_controls`
- `paper_position_marks`
- `paper_position_lifecycle_events`

## Next milestone

Milestone 50 will connect the Daily Scanner, institutional decision, portfolio construction, risk gateway, canonical order management, and paper execution into one governed workflow using these authoritative repositories.
