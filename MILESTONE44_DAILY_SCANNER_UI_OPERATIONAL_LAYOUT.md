# Milestone 44 Daily Scanner UI Operational Layout

This drop-in updates the Daily Scanner workstation page with:

- full-width content and no-wrap candidate columns;
- sticky Best Trade Candidates table headers;
- click-to-expand/click-to-collapse ranking explanations;
- score, positive contributor, constraint, contract-selection, and freshness sections;
- a compact database-readiness panel in place of provider health and lineage;
- a reduced global header containing only Trading Operations Workstation;
- removal of the Data architecture panel.

## Install

From the TradingPlatform directory:

```bash
 tar -xzf ~/Downloads/TradingPlatform_Milestone44_DailyScanner_UI_OperationalLayout_20260724.tar.gz --strip-components=1
```

## Rebuild

```bash
cd ui/workstation
rm -rf node_modules
npm install
npm run build
```

## Validate

```bash
uv run python scripts/test_m44_daily_scanner_ui_operational_layout.py
cd ui/workstation
npm test
npm run typecheck
npm run build
```
