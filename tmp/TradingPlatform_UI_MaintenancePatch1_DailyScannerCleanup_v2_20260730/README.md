# UI Maintenance Patch 1 v2 — Daily Scanner Cleanup

Built from the uploaded post–UI Milestone 9 `src/pages.tsx` baseline.

## Changes

- Removes the entire **Market ingestion** card from the Daily Scanner.
- Removes **Run governed ingestion before scanning** from Scan Controls.
- Preserves scan behavior, scanner API contracts, and Option Scanner persisted-snapshot governance.

## Apply

```bash
cd /Users/vinay.hatti/TradingPlatform

tar -xzf ~/Downloads/TradingPlatform_UI_MaintenancePatch1_DailyScannerCleanup_v2_20260730.tar.gz -C /tmp

/tmp/TradingPlatform_UI_MaintenancePatch1_DailyScannerCleanup_v2_20260730/APPLY_UI_MAINTENANCE_PATCH1_DAILY_SCANNER_CLEANUP_V2.sh \
  /Users/vinay.hatti/TradingPlatform
```

## Validate

```bash
cd /Users/vinay.hatti/TradingPlatform/ui/workstation
TARGET_ROOT="$PWD" node --test /tmp/TradingPlatform_UI_MaintenancePatch1_DailyScannerCleanup_v2_20260730/tests/daily-scanner-cleanup-v2.test.mjs
npm run typecheck
npm run build
```

## Rollback

```bash
/tmp/TradingPlatform_UI_MaintenancePatch1_DailyScannerCleanup_v2_20260730/ROLLBACK_UI_MAINTENANCE_PATCH1_DAILY_SCANNER_CLEANUP_V2.sh \
  /Users/vinay.hatti/TradingPlatform
```
