# Milestone 70 — Institutional Execution Intelligence

## Status
COMPLETE — cumulative release through M70.3.

## Purpose
Milestone 70 closes the gap between an approved institutional option trade and the market actually routed to IBKR paper trading. Research and strategy generation continue to use governed persisted Polygon snapshots; execution uses a direct Polygon exact-contract preflight immediately before routing and during working-order assessment.

## Architecture
Approved Trade Plan → Execution Intent → direct Polygon multi-sample quote → midpoint/executable repricing → execution confidence/risk/envelope checks → governed smart limit → IBKR paper route → broker synchronization → immutable fill telemetry → working-order assessment/reprice → execution-quality/learning records.

## Major capabilities
- Direct Polygon exact option-contract and underlying lookup at execution time; no persisted-snapshot fallback.
- Polygon `last_quote.last_updated` nanosecond timestamp compatibility and explicit missing-timestamp governance.
- Multi-sample quote stability and execution-confidence scoring.
- Separate market drift (approved reference to fresh midpoint) from crossing/slippage cost (fresh midpoint to executable bid/ask).
- Governed smart initial limit between midpoint and immediately executable market, bounded by the approval envelope.
- Fresh Trade Builder economics/max-loss/risk-budget revalidation.
- Immutable execution snapshots and events.
- Order lifecycle telemetry, fill events, commissions, fill rate, realized slippage, and execution-quality score.
- Working-order intelligence with CONTINUE / REPRICE / CANCEL recommendations.
- Paper-only, confirmation-gated in-place IBKR reprice using the existing broker order id.
- Execution learning samples for later M65 calibration; no automatic model retraining in M70.
- Execution Intelligence Operations page with lifecycle and quality metrics.

## Governance
Live trading remains disabled. All routing remains bound to verified IBKR paper accounts. Direct Polygon failure, missing/expired quote timestamps, risk-budget failure, defined-risk failure, or approved-envelope breach fail closed. Working-order repricing requires an explicit operator confirmation and never changes broker order identity.

## Configuration
The following `.env` keys are supported and reread by policy loading:

- `TRADING_AI_EXECUTION_DIRECT_POLYGON_ENABLED=true`
- `TRADING_AI_EXECUTION_MAX_QUOTE_AGE_SECONDS=15`
- `TRADING_AI_EXECUTION_MAX_PRICE_DRIFT_PCT=3`
- `TRADING_AI_EXECUTION_QUOTE_STABILITY_SAMPLES=3`
- `TRADING_AI_EXECUTION_QUOTE_STABILITY_INTERVAL_MS=300`
- `TRADING_AI_EXECUTION_MIN_CONFIDENCE=70`
- `TRADING_AI_EXECUTION_MAX_SPREAD_PCT=100`
- `TRADING_AI_EXECUTION_MIN_EDGE_SCORE=0`
- `TRADING_AI_EXECUTION_MIN_EXPECTED_VALUE=-1e18`
- `TRADING_AI_EXECUTION_MIN_RETURN_ON_RISK=-1e18`
- `TRADING_AI_EXECUTION_INITIAL_LIMIT_AGGRESSION_PCT=35`
- `TRADING_AI_EXECUTION_WORKING_REPRICE_AFTER_SECONDS=8`
- `TRADING_AI_EXECUTION_WORKING_REPRICE_MIN_CHANGE_PCT=0.25`
- `TRADING_AI_EXECUTION_MAX_REPRICES=4`
- `TRADING_AI_EXECUTION_WORKING_ORDER_MAX_AGE_SECONDS=180`

The edge/EV/return/spread defaults intentionally preserve existing upstream decision policy; they can be tightened later without source changes.

## Migrations
- `m70_001` — execution snapshots/events
- `m70_002` — nullable quote age / timestamp compatibility
- `m70_003` — order telemetry, fill events, working-order assessments, execution learning samples

## Acceptance
Run:

```bash
uv run alembic upgrade head
uv run python scripts/verify_m70_execution_intelligence.py
uv run python -m pytest -q tests/test_m70_execution_intelligence.py tests/test_m70_polygon_quote_timestamp_compatibility.py
```

Then validate one liquid IBKR paper execution end-to-end and synchronize broker status until terminal.
