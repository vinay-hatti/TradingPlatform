# Daily Scanner UI panel-order update

## Change

Moves the existing **Run history** panel immediately before the existing **Best trade candidates** panel on the Daily Scanner page.

No sizing or styling was changed:

- `Run history` retains `compact` and `run-history-scroll`.
- `Best trade candidates` retains its existing non-compact `Card`.
- No CSS, grid, width, height, table, or responsive classes were modified.

## Install

From the TradingPlatform project root:

```bash
cp ui/workstation/src/pages.tsx \
  ui/workstation/src/pages.tsx.before_panel_order_fix

tar -xzf ~/Downloads/daily_scanner_ui_panel_order_dropin.tar.gz \
  --strip-components=1
```

## Validate on macOS

```bash
cd ui/workstation
npm test
npm run typecheck
npm run build
```

Restart the UI process if it is already running.
