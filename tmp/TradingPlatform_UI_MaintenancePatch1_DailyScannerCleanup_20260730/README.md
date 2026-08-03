# UI Maintenance Patch 1 — Daily Scanner Workflow Cleanup

Removes only these Daily Scanner UI elements:

1. The **Market Ingestion** panel/section.
2. The **Run governed ingestion before scanning** control in Scan Controls.

The patch does not modify backend APIs, scanner algorithms, ingestion orchestration, database schema, provider behavior, or publication governance.

## Apply

```bash
cd /Users/vinay.hatti/TradingPlatform
tar -xzf ~/Downloads/TradingPlatform_UI_MaintenancePatch1_DailyScannerCleanup_20260730.tar.gz -C /tmp
/tmp/TradingPlatform_UI_MaintenancePatch1_DailyScannerCleanup_20260730/APPLY_UI_MAINTENANCE_PATCH1_DAILY_SCANNER_CLEANUP.sh /Users/vinay.hatti/TradingPlatform
```

## Validate

```bash
cd /Users/vinay.hatti/TradingPlatform/ui/workstation
node --test tests/daily-scanner-workflow-cleanup.test.mjs
npm test
npm run typecheck
npm run build
```

## Roll back

```bash
/tmp/TradingPlatform_UI_MaintenancePatch1_DailyScannerCleanup_20260730/ROLLBACK_UI_MAINTENANCE_PATCH1_DAILY_SCANNER_CLEANUP.sh /Users/vinay.hatti/TradingPlatform
```
