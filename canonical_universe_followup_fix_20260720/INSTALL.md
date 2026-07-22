# Canonical Universe Follow-up Fix

Copy the included `src/` tree into the TradingPlatform repository root.

This fixes:

1. Canonical-only publication validation no longer compares the authoritative CSV to a stale universe-refresh manifest.
2. External market-data requests use `provider_symbol` from the canonical CSV (`BRK-B`, `BF-B`).
3. Stored `price_history.symbol` values remain canonical (`BRK.B`, `BF.B`).

Run:

```bash
uv run python -m trading_ai refresh-market-universe --minimum-symbol-count 500
uv run python -m trading_ai refresh-market-universe --minimum-symbol-count 500 --populate-market-data
```
