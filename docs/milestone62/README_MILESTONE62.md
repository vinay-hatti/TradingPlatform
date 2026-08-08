# Milestone 62 — Institutional Options Generator

Milestone 62 adds a parallel, underlying-first Institutional Options workflow while preserving the existing Daily Scanner and Option Scanner workflows.

## Workflow

1. Consume persisted `current_stock_intelligence` opportunities.
2. Validate freshness, lineage, direction, structure, and dynamic management.
3. Generate multiple regime-compatible option strategies.
4. Optimize DTE, expiration, strikes, and exact Polygon option contracts.
5. Compare calibrated probability, expected value, return on risk, liquidity, capital efficiency, tail risk, and complexity.
6. Select one governed recommendation while preserving alternatives and rejection reasons.
7. Propagate the underlying thesis and dynamic management into Trade Builder and Execution Workspace.
8. Capture immutable outcomes and produce setup/strategy/regime/management calibration analytics.

## New page

`#/institutional-options`

## API root

`/api/v1/institutional-options`

## Migrations

`m61_010 -> m62_001 -> m62_002 -> m62_003 -> m62_004`

## Operational activation

The release is additive. It does not replace or redirect the Daily Scanner or Option Scanner. Populate Institutional Options by calling the governed ingestion/generation APIs or their services after Stock Intelligence and Polygon options data have been published.
