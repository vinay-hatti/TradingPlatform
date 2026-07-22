Canonical publication validation fix

Install from the TradingPlatform repository root:
  unzip -o canonical_publication_validation_fix_20260720.zip

Then run:
  uv run python -m trading_ai refresh-market-universe --minimum-symbol-count 500

Behavior:
- data/universe/us_listed_equities_etfs.csv remains authoritative.
- A stale universe_manifest checksum is ignored when the universe was not rebuilt in the current run.
- Universe count is read directly from the canonical CSV in canonical-only mode.
- Rebuilt-universe runs still require and validate universe_manifest.
