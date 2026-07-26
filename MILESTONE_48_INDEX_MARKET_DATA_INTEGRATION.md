# Milestone 48 — Authoritative Index Market Data Integration

## Objective

Extend `scripts/run_market_ingestion.py` so it remains the sole production ingestion entry point while supporting SPX, NDX, and Russell 2000 cash-index data.

## Canonical symbols

The application, database, scanner, reports, lineage, and replay continue to use:

- `SPX`
- `NDX`
- `RUT`

Polygon-specific identifiers are resolved only inside provider adapters:

| Canonical | Polygon index OHLC | Polygon option snapshot | Polygon option reference |
|---|---|---|---|
| SPX | I:SPX | I:SPX | SPX |
| NDX | I:NDX | I:NDX | NDX |
| RUT | I:RUT | I:RUT | RUT |

`RUT` is used for the Russell 2000 cash index. `RTY` is not added because it is normally associated with Russell 2000 futures.

## Authoritative registries

- `data/universe/us_listed_equities_etfs.csv`
- `data/universe/us_market_indices.csv`

The ingestion command combines both approved registries into one canonical instrument registry.

## Provider routing

- EQUITY and ETF OHLCV: existing Yahoo path
- INDEX OHLC: Polygon index aggregate path
- All listed options snapshots: Polygon

Cash-index aggregate volume is normalized to `0.0` to preserve the existing non-null `MarketBar` contract. Downstream logic must not use underlying volume filters for `asset_class=INDEX`.

## Commands

All governed instruments:

```bash
uv run python scripts/run_market_ingestion.py
```

Indices only:

```bash
uv run python scripts/run_market_ingestion.py --asset-classes INDEX
```

Specific indices:

```bash
uv run python scripts/run_market_ingestion.py --symbols SPX,NDX,RUT
```

Underlying index bars only:

```bash
uv run python scripts/run_market_ingestion.py \
  --symbols SPX,NDX,RUT \
  --data-scope underlying
```

Index options only:

```bash
uv run python scripts/run_market_ingestion.py \
  --symbols SPX,NDX,RUT \
  --data-scope options
```

## Validation

```bash
uv run python scripts/test_authoritative_index_ingestion.py
uv run python scripts/test_m43_market_ingestion_symbol_sources.py
uv run python scripts/test_market_ingestion_contract.py
```
