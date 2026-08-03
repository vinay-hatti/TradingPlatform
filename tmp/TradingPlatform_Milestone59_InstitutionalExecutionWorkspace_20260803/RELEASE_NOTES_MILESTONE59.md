# Milestone 59 Release Notes

## New database objects

- `execution_intents`
- `execution_intent_audit_events`

## New REST endpoints

- `GET /api/v1/execution-workspace/intents`
- `POST /api/v1/execution-workspace/intents/from-trade-plan/{trade_plan_id}`
- `POST /api/v1/execution-workspace/intents/{id}/transitions`
- `POST /api/v1/execution-workspace/intents/{id}/submit`
- `POST /api/v1/execution-workspace/intents/{id}/synchronize`
- `POST /api/v1/execution-workspace/intents/{id}/cancel`
- `GET /api/v1/execution-workspace/intents/{id}/audit`
- `GET /api/v1/execution-workspace/routing-status/{portfolio_id}`

## Lifecycle

`PAPER_READY → VALIDATED → APPROVED → SUBMITTED → ACKNOWLEDGED/PARTIALLY_FILLED → FILLED`

Terminal alternatives: `CANCELLED`, `REJECTED`, `EXPIRED`.

## Compatibility

The release preserves the existing Opportunity, Institutional Intelligence, Trade Builder, IBKR Paper, Portfolio Intelligence, and Performance Learning contracts.
