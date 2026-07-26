# Install and Validate — Authoritative Index Ingestion

## Install

From the repository root:

```bash
tar -xzf ~/Downloads/TradingPlatform_Milestone48_AuthoritativeIndexIngestion_20260725.tar.gz --strip-components=1
```

No database migration is required.

## Validate contracts

```bash
uv run python scripts/test_authoritative_index_ingestion.py
uv run python scripts/test_m43_market_ingestion_symbol_sources.py
uv run python scripts/test_market_ingestion_contract.py
```

## Verify canonical mapping

```bash
uv run python - <<'PY'
from trading_ai.market.instruments import CanonicalInstrumentRegistry

registry = CanonicalInstrumentRegistry.from_files((
    "data/universe/us_listed_equities_etfs.csv",
    "data/universe/us_market_indices.csv",
))
for symbol in ("SPX", "NDX", "RUT"):
    item = registry.get(symbol)
    print(symbol, item.price_ticker, item.options_snapshot_ticker, item.options_reference_ticker)
PY
```

Expected:

```text
SPX I:SPX I:SPX SPX
NDX I:NDX I:NDX NDX
RUT I:RUT I:RUT RUT
```

## Live index underlying smoke test

```bash
uv run python scripts/run_market_ingestion.py \
  --symbols SPX,NDX,RUT \
  --data-scope underlying \
  --lookback-days 30 \
  --force-refresh \
  --continue-on-error \
  --skip-market-overview
```

## Live index options smoke test

```bash
uv run python scripts/run_market_ingestion.py \
  --symbols SPX,NDX,RUT \
  --data-scope options \
  --options-minimum-dte 7 \
  --options-maximum-dte 60 \
  --force-refresh \
  --continue-on-error \
  --skip-dealer-positioning \
  --skip-market-overview
```
