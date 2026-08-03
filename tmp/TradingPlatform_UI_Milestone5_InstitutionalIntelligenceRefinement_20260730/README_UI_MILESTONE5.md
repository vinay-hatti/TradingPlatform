# UI Milestone 5 — Institutional Intelligence Workspace Refinement

This package upgrades `#/intelligence` without changing intelligence APIs, persistence, scoring, or workflow governance.

## Apply
`./APPLY_UI_MILESTONE5_INSTITUTIONAL_INTELLIGENCE.sh /Users/vinay.hatti/TradingPlatform`

## Validate
From `ui/workstation`:
- `node tests/ui-milestone5-institutional-intelligence.test.mjs`
- `npm test`
- `npm run typecheck`
- `npm run build`

The package assumes UI Milestones 1–4 and the Shell Recovery Fix are already installed.
