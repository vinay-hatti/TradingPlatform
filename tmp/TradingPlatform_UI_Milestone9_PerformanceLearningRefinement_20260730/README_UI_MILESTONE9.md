# UI Milestone 9 — Performance Analytics & Continuous Learning Refinement

This package replaces the existing Performance Learning route with an institutional analytics workspace while preserving the Milestone 58 REST contracts and governance model.

## Apply

```bash
./APPLY_UI_MILESTONE9_PERFORMANCE_LEARNING.sh /Users/vinay.hatti/TradingPlatform
```

## Validate

```bash
cd /Users/vinay.hatti/TradingPlatform/ui/workstation
node tests/ui-milestone9-performance-learning.test.mjs
npm test
npm run typecheck
npm run build
```

Open `#/performance-learning`.

## Scope

- Portfolio performance KPI ribbon
- Strategy and directional attribution
- Probability calibration
- Decision-quality metrics
- Governed learning recommendations
- Versioned policy registry and policy inspection
- Route-local responsive styles

No scanner weights, probability models, risk limits, trade plans, or broker controls are changed automatically.
