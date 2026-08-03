# Milestone 53 — Institutional Option Scanner Workspace

## Phase 1 — Shared Workspace Framework, Clone, and Routing

This package leaves the current **Daily Scanner** page operational and adds a parallel **Option Scanner** page at `#/option-scanner`.

### Delivered

- A reusable `ScannerWorkspacePage` configuration framework.
- Existing `DailyScannerPage` converted to a thin configured wrapper without changing its backend contract.
- New `OptionScannerPage` cloned from the proven Daily Scanner workflow.
- New left-navigation entry and route.
- Separate browser preference namespaces:
  - `trading-ai:daily-scanner:scan-controls`
  - `trading-ai:option-scanner:scan-controls`
- Both pages intentionally use the current scanner APIs and database-only scan workflow during the side-by-side evaluation period.
- No database migration and no backend schema change.

### Apply

```bash
cd /Users/vinay.hatti/TradingPlatform
tar -xzf ~/Downloads/TradingPlatform_Milestone53_Phase1_OptionScannerWorkspace_20260730.tar.gz -C /tmp
/tmp/TradingPlatform_Milestone53_Phase1_OptionScannerWorkspace_20260730/APPLY_M53_PHASE1_OPTION_SCANNER.sh /Users/vinay.hatti/TradingPlatform
```

### Validate

```bash
cd /Users/vinay.hatti/TradingPlatform
PYTHONPATH=src uv run python scripts/test_m53_phase1_option_scanner_workspace.py
cd ui/workstation
npm run typecheck
npm test
npm run build
```

### Side-by-side URLs

- Daily Scanner: `http://127.0.0.1:5173/#/scanner`
- Option Scanner: `http://127.0.0.1:5173/#/option-scanner`

### Scope boundary

Phase 1 deliberately keeps the Option Scanner behavior identical to Daily Scanner. The sectioned institutional controls, strategy engine, progressive disclosure modes, dealer/transition/institutional filters, saved workspaces, and opportunity builder belong to later cumulative phases.
