# Milestone 62 Formal Acceptance Review

## Status

**Source acceptance: PASSED**  
**Operational acceptance on the user's Mac/PostgreSQL/Polygon/IBKR environment: requires installation and smoke validation.**

## Approved acceptance criteria

| # | Criterion | Source evidence | Status |
|---|---|---|---|
| 1 | Existing Daily Scanner and Option Scanner remain available and are not replaced | New route is parallel under `institutional-options`; existing route keys remain registered | PASS |
| 2 | New workflow starts from persisted Stock Intelligence | Opportunity ingestion reads persisted Stock Intelligence publication and preserves scanner lineage | PASS |
| 3 | No strategy is generated without a valid underlying thesis | Eligibility and thesis validation precede strategy generation | PASS |
| 4 | Multiple compatible strategies are ranked for one underlying | Strategy generation and comparison persist eligible and rejected alternatives | PASS |
| 5 | Every option leg uses exact Polygon identity | Contract optimization and handoff require non-empty unique `option_symbol` values | PASS |
| 6 | Strategy selection accounts for regime, IV, Greeks, liquidity, and capital efficiency | Contract optimizer and valuation layer score these components | PASS |
| 7 | Final probability is explainable and calibration-ready | Probability decomposition plus outcome Brier/log-loss/ECE analytics | PASS |
| 8 | Underlying structural stops and dynamic exits flow into Trade Builder and Execution Workspace | Execution recommendations and handoff metadata preserve entry/stop/targets/trailing | PASS |
| 9 | Fixed premium TP/SL is only an emergency fallback | Underlying structural management is primary; emergency option stop remains a safeguard | PASS |
| 10 | Outcomes are stored for setup and strategy calibration | Immutable observations and learning snapshots by setup/strategy/regime/management | PASS |

## Release validation

- Milestone 62 tests: **61 passed**
- Milestone 61 + 62 tests: **166 passed**
- Canonical Python modules: **1,647 compiled, 0 errors**
- TypeScript: **passed**
- Alembic head supplied by release: **m62_004**

## Required local smoke validation

1. Install package and run `uv run alembic upgrade head`.
2. Rebuild/restart API and workstation.
3. Ingest Institutional Options opportunities from `current_stock_intelligence`.
4. Generate strategies, optimize contracts, value strategies, and generate management for a small symbol set.
5. Verify exact Polygon symbols in all selected legs.
6. Create a Trade Builder handoff and verify dynamic management lineage.
7. Create a paper Execution Intent only after the plan reaches `PAPER_READY`.
8. Capture one test outcome and generate a learning summary.

The milestone should be considered operationally accepted only after these environment-specific smoke checks pass.
