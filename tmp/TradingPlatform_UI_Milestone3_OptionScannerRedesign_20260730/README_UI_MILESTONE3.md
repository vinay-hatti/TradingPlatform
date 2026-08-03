# UI Milestone 3 — Institutional Option Scanner Redesign

This cumulative UI release modernizes the existing scanner routes without changing scanner algorithms, REST contracts, database schemas, or provider rules.

## Apply

```bash
./APPLY_UI_MILESTONE3_OPTION_SCANNER.sh /Users/vinay.hatti/TradingPlatform
```

## Validate

```bash
cd /Users/vinay.hatti/TradingPlatform/ui/workstation
npm test
npm run typecheck
npm run build
```

## Functional validation

1. Open `#/option-scanner` or the existing scanner route.
2. Verify KPI context, filter controls, presets, opportunity grid, and intelligence panel.
3. Run a governed scan and confirm results use the existing persisted scanner API.
4. Select a row and verify Opportunity, Intelligence, and Trade Builder navigation.
5. Confirm favorites and presets survive a browser refresh.
