# UI Milestone 7 — Portfolio Intelligence Command Center Refinement

This package replaces the legacy Portfolio route with a route-local institutional command center while preserving the Milestone 57 managed-position and portfolio-intelligence contracts.

## Apply

```bash
./APPLY_UI_MILESTONE7_PORTFOLIO_INTELLIGENCE.sh /Users/vinay.hatti/TradingPlatform
```

## Validate

```bash
cd /Users/vinay.hatti/TradingPlatform/ui/workstation
node tests/ui-milestone7-portfolio-intelligence.test.mjs
npm test
npm run typecheck
npm run build
```

Open `#/portfolio`.
