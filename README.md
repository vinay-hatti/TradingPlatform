# TradingAI / TradingPlatform

TradingPlatform is an institutional-style, underlying-first options
intelligence, portfolio, paper-execution, autonomous-management,
performance-learning, and governed-research platform.

## End-to-End Workflow

``` text
Market / Event Data
 -> Market Overview / Market Intelligence
 -> Trend Intelligence
 -> Stock Intelligence
 -> Institutional Options / Valuation / Inflection
 -> Institutional Decision Intelligence
 -> Portfolio Risk & Capital Allocation
 -> Advanced Trade Builder
 -> Execution Intelligence / OMS
 -> IBKR Paper Broker Truth
 -> Autonomous Position Management
 -> Performance / Outcome Learning
```

M77 and M78 provide isolated historical/prospective research. M78 Setup
Intelligence is shadow-only and cannot automatically change production.

## Core Principles

-   Deterministic and explainable decisions.
-   Explicit authority lineage and freshness.
-   Fail-closed governance.
-   Portfolio-aware rather than candidate-isolated decisions.
-   Exact option-contract identity.
-   Broker truth for actual orders/fills/positions.
-   Research isolation and no automatic model/champion promotion.
-   Current execution environment is IBKR Paper.

## Technology

-   macOS.
-   Python 3.13 via `uv`.
-   PostgreSQL 17.
-   SQLAlchemy 2.x / Alembic.
-   FastAPI / Uvicorn.
-   React / TypeScript / Vite.
-   macOS launchd / LaunchAgents.
-   Polygon market data.
-   Interactive Brokers Paper.
-   Alpha Vantage earnings.
-   Federal Reserve / BLS / BEA macro events.

## Repository Layout

``` text
TradingPlatform/
  src/trading_ai/       backend packages
  scripts/              operational/research entry points
  migrations/           Alembic migrations
  ui/workstation/       React/TypeScript workstation
  tests/                regression/focused tests
  data/                 universe/research artifacts
  reports/              generated evidence/reports
  logs/                 operational logs
  backups/              installer/runtime backups
```

Major backend areas include Market/Market Intelligence, Trend
Intelligence, Institutional Options, Option Valuation, Inflection
Intelligence, Institutional Intelligence, Portfolio Intelligence/Risk
Allocation, Trade Builder, Execution
Intelligence/Orchestration/Workspace, broker synchronization,
Dynamic/Autonomous Position Management, Performance Learning, M77
research, and M78 Setup Intelligence.

## Database

Current Alembic head: `m78_001`.

Use the current database-session pattern:

``` python
from trading_ai.database.session import SessionLocal

session = SessionLocal()
try:
    bind = session.get_bind()
finally:
    session.close()
```

Apply migrations:

``` bash
cd /Users/vinay.hatti/TradingPlatform
uv run alembic upgrade heads
uv run alembic heads
```

## Dependency Setup

``` bash
cd /Users/vinay.hatti/TradingPlatform
uv sync --all-groups
uv run python --version
uv run python -c "import trading_ai; print(trading_ai.__file__)"
```

Workstation:

``` bash
cd ui/workstation
npm ci
npm test
npm run typecheck
npm run build
```

## Provider Policy

-   Polygon: authoritative current underlying/options market data.
-   IBKR: paper broker/account/order/fill truth.
-   Alpha Vantage: earnings calendar.
-   Federal Reserve: FOMC.
-   BLS: CPI/PPI/Employment/JOLTS.
-   BEA: GDP/PCE/Personal Income.

## Normal User Workflow

1.  Confirm current ingestion/authorities are READY.
2.  Start with Market Overview.
3.  Review Daily Scanner and Stock Scanner.
4.  Validate multi-timeframe underlying thesis and structural
    invalidation.
5.  Review Institutional Options strategies and exact contracts.
6.  Review valuation/mispricing and inflection/timing.
7.  Require current Institutional Decision Intelligence.
8.  Require current portfolio-aware risk/allocation.
9.  Build the exact trade plan in Advanced Trade Builder.
10. Revalidate strategy, portfolio and fresh quotes.
11. Execute only after paper preflight passes.
12. Reconcile IBKR broker truth.
13. Verify autonomous position management.
14. Review realized outcome/performance after closure.

## M78 Setup Intelligence

M78 detects explicit setup archetypes including trend
pullback/continuation, breakout/breakdown lifecycle, failed
breakout/breakdown reversal, and support/resistance reversal.

``` bash
uv run python scripts/run_m78_setup_intelligence.py capture
uv run python scripts/run_m78_setup_intelligence.py materialize-outcomes
uv run python scripts/run_m78_setup_intelligence.py status
```

Do not force training while readiness is `INSUFFICIENT_EVIDENCE`.

M78 governance:

-   automatic training: false;
-   automatic activation: false;
-   automatic certification: false;
-   authority effect: false.

## Current Scheduled Services

  Service                       Schedule
  ----------------------------- --------------------------------------------------
  Futures pre-open              Mon-Fri 07:55
  Event intelligence            Mon-Fri 08:10
  Morning ingestion             Mon-Fri 08:30
  Intraday options              Mon-Fri 09:30, 10:30, 11:30, 12:30, 13:30, 14:30
  End-of-day ingestion          Mon-Fri 15:20
  Combined M77 -\> M78 shadow   Mon-Fri 18:30

The combined research job runs M77 first and permits M78 only after an
explicit M77 READY marker.

Continuous broker sync, production operations, dynamic management,
portfolio intelligence and entry-fill management remain independent.

## Validation

Typical validation commands:

``` bash
cd /Users/vinay.hatti/TradingPlatform

uv run alembic heads
uv run pytest -q
uv run python scripts/verify_m78_release.py
uv run python -m pytest -q tests/m78

cd ui/workstation
npm test
npm run typecheck
npm run build
```

## Paper-Trading Safety

Before submitting any order:

-   runtime/account must be PAPER;
-   current Stock/Decision/Portfolio authorities must be READY;
-   exact contract identity must be validated;
-   Trade Builder revalidation must pass;
-   execution quotes must be fresh;
-   IBKR price/tick rules must pass;
-   autonomous management should be healthy before relying on automated
    exits.

Positions must be closed before expiration. Multi-leg structures use the
earliest leg expiration for the expiration-exit guardrail.

## Research Governance

M77 historical discovery is closed and prospective protocols are
accumulating evidence.

M78 is accumulating setup evidence and currently has no production
authority. Research success never automatically changes production
thresholds, weights, strategy selection, portfolio allocation,
execution, or management.

## Current Priorities

-   Keep weekday ingestion healthy.
-   Keep the M77 -\> M78 nightly research chain healthy.
-   Accumulate M77/M78 prospective evidence.
-   Maintain broker reconciliation and autonomous management.
-   Continue performance/calibration review.
-   Keep live-capital execution disabled until separately certified.
-   Preserve deterministic, explainable, fail-closed governance.

## Detailed Project Status

See `PROJECT_STATUS.md` for milestone-by-milestone status, current
research state, automation schedules, and open items.
