# Milestone 53 Phase 2 — Option Scanner Workspace Redesign

This package redesigns only the Option Scanner page. Daily Scanner retains its existing layout and API behavior.

## Delivered

- Basic, Advanced, and Professional workspace depth modes.
- Independent persistence of the selected workspace depth.
- Sectioned Option Scanner controls:
  - Opportunity definition
  - Contract horizon
  - Data readiness
  - Professional ingestion operations
- Workspace summary strip for universe, horizon, and data policy.
- Sticky `Find Opportunities` action bar.
- Responsive desktop, tablet, and mobile layouts.
- No backend contract, database schema, or scanner request changes.

## Progressive disclosure

- **Basic:** universe, score, opportunity count, expiration mode.
- **Advanced:** adds custom symbols, DTE bounds, diversification, and refresh policy.
- **Professional:** adds coverage/failure governance and independent ingestion operations.

## Apply

```bash
cd /Users/vinay.hatti/TradingPlatform

tar -xzf ~/Downloads/TradingPlatform_Milestone53_Phase2_OptionScannerWorkspaceRedesign_20260730.tar.gz -C /tmp

/tmp/TradingPlatform_Milestone53_Phase2_OptionScannerWorkspaceRedesign_20260730/APPLY_M53_PHASE2_OPTION_SCANNER.sh \
  /Users/vinay.hatti/TradingPlatform
```

## Validate

```bash
cd /Users/vinay.hatti/TradingPlatform
PYTHONPATH=src uv run python scripts/test_m53_phase2_option_scanner_workspace.py
cd ui/workstation
npm run typecheck
npm test
npm run build
```

## Rollback

```bash
/tmp/TradingPlatform_Milestone53_Phase2_OptionScannerWorkspaceRedesign_20260730/ROLLBACK_M53_PHASE2_OPTION_SCANNER.sh \
  /Users/vinay.hatti/TradingPlatform
```
