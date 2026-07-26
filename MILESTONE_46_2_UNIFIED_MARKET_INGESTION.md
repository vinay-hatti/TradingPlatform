# Milestone 46.2 — Unified Polygon Market Ingestion

`run_market_ingestion.py` is the authoritative loader for the TradingPlatform.

## Provider policy

- Polygon: underlying OHLCV, options snapshots, option quote data and all persisted raw market inputs.
- No Yahoo provider is instantiated by this command.
- Derived analytics are calculated internally from persisted Polygon data.
- Full order-book depth remains `CAPABILITY_UNAVAILABLE` and is never fabricated.

## Pipeline phases

1. `underlying_ohlcv`
2. `polygon_options_compatibility`
3. `timestamped_option_snapshot`
4. `volatility_snapshots`
5. `liquidity_snapshots`
6. `dealer_positioning`
7. `market_overview`
8. `market_intelligence`

The compatibility options phase retains the existing `option_contract_history` writer so the Daily Scanner remains backward-compatible. The timestamped phase then publishes the capture into `option_snapshot_run` and `option_contract_snapshot` for replay and historical analytics.

## Default command

```bash
uv run python scripts/run_market_ingestion.py \
  --universe-file data/universe/us_listed_equities_etfs.csv \
  --data-scope all \
  --continue-on-error
```

## Outputs

- `reports/market_ingestion/unified_latest.json`
- `reports/market_ingestion/options_latest.json`
- `reports/market_ingestion/dealer_positioning_latest.json`
- Persisted Market Overview and Market Intelligence snapshots

## New skip controls

- `--skip-timestamped-options`
- `--skip-volatility-snapshots`
- `--skip-liquidity-snapshots`
- Existing dealer, overview and intelligence skip controls remain supported.

## Readiness semantics

- `READY`: phase completed normally.
- `DEGRADED`: usable output was produced with incomplete coverage.
- `FAILED`: phase failed.
- `SKIPPED`: explicitly disabled or inapplicable to the selected scope.

With `--continue-on-error`, later independent phases continue and the unified report records all failures. Without it, a failed required phase aborts the run.

## Important AC-9 boundary

The Polygon options snapshot endpoint provides contract quote and volume summaries. The unified ingestion command therefore persists snapshot liquidity metrics now. Average trade size and effective-spread metrics remain unavailable until a separate Polygon trades/quotes event capture is enabled; they are not inferred from snapshot volume.
