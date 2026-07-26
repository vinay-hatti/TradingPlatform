# Milestone 48 — Index Dealer Positioning Market Overview Fix

## Problem

The Market Overview requested dealer snapshots using canonical symbols (`SPX`, `NDX`, `RUT`) only. Existing rows can carry Polygon or legacy aliases (`I:SPX`, `I:NDX`, `I:RUT`, or `RTY`), so those rows were omitted from the Dealer positioning & options structure panel.

## Resolution

The Market Overview dealer resolver now:

- expands canonical index symbols to all supported persistence aliases;
- queries dealer snapshots case-insensitively;
- canonicalizes returned rows to `SPX`, `NDX`, and `RUT`;
- records `source_symbol` for audit visibility;
- selects the newest row per canonical symbol;
- keeps ETFs and sector ETFs unchanged.

The UI continues to render canonical symbols only.
