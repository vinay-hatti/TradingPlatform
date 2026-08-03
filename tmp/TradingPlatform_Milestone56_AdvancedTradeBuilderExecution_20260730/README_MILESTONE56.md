# Milestone 56 — Advanced Trade Builder & Execution

This cumulative package builds on Milestone 55 and introduces the governed handoff from canonical Opportunity intelligence to execution-ready paper-order intent.

## Capabilities

- Versioned trade plans tied to `opportunity_id`, Opportunity version, and latest intelligence snapshot.
- Up to four option legs in the API contract; workstation initially exposes single-leg and vertical-spread construction.
- Debit, credit, maximum-loss, maximum-profit, reward/risk, and risk-budget calculations.
- Net Delta, Gamma, Theta, and Vega aggregation.
- Validation for quantities, expiry coherence, leg count, defined risk, and account risk budget.
- Optimistic version conflict protection and append-only audit history.
- Lifecycle: `DRAFT`, `VALIDATED`, `APPROVED`, `PAPER_READY`, `CANCELLED`.
- `PAPER_READY` creates an execution intent only. Existing IBKR paper-account governance remains authoritative; live trading stays disabled.

## Apply

```bash
cd /Users/vinay.hatti/TradingPlatform
tar -xzf ~/Downloads/TradingPlatform_Milestone56_AdvancedTradeBuilderExecution_20260730.tar.gz -C /tmp
/tmp/TradingPlatform_Milestone56_AdvancedTradeBuilderExecution_20260730/APPLY_MILESTONE56_ADVANCED_TRADE_BUILDER_EXECUTION.sh /Users/vinay.hatti/TradingPlatform
uv run alembic upgrade head
```

## Validate

```bash
cd /Users/vinay.hatti/TradingPlatform
PYTHONPATH=src uv run python scripts/test_m56_advanced_trade_builder.py
cd ui/workstation
npm run typecheck
npm test
npm run build
```

Expected Python result:

```text
Milestone 56 Advanced Trade Builder assertions passed.
```

## API

- `GET /api/v1/trade-builder/plans`
- `POST /api/v1/trade-builder/plans`
- `POST /api/v1/trade-builder/plans/{trade_plan_id}/transitions`
- `GET /api/v1/trade-builder/plans/{trade_plan_id}/audit`

## Workstation

Open `#/trade-builder` after starting the workstation.
