# Milestone 44 Intraday Post-Ingestion Refresh

`run_market_ingestion.py` now refreshes Milestone 44 derived analytics automatically after every successful options ingestion.

## Default flow

```text
Polygon option snapshot
  -> option_contract_history insert/update
  -> Milestone 44 persisted-snapshot analytics
  -> dealer_position_snapshot merge
  -> dealer_strike_profile replace for symbol/date
  -> dealer_expiration_profile replace for symbol/date
  -> iv_surface_snapshot replace for symbol/date
  -> reports/market_ingestion/dealer_positioning_latest.json
```

Repeated runs on the same trading date update the current daily state. They do not create duplicate derived rows because the normalized tables are keyed by symbol and `as_of_date` (plus expiry/strike/type for child tables).

## Recommended intraday command

```bash
uv run python scripts/run_market_ingestion.py \
  --data-scope options \
  --options-minimum-dte 1 \
  --options-maximum-dte 180 \
  --force-refresh \
  --continue-on-error
```

Note: per-symbol Milestone 44 reports are disabled by default in this package, so the final flag above is not required. Use `--dealer-positioning-write-reports` only when HTML/CSV/JSON artifacts are wanted for every symbol.

## Controls

- `--skip-dealer-positioning`: ingest raw options only.
- `--dealer-positioning-write-reports`: write per-symbol reports in addition to database persistence.
- `--dealer-positioning-fail-fast`: abort if a Milestone 44 symbol refresh fails.
- `--dealer-positioning-report PATH`: change the consolidated refresh profile location.
- `--dealer-positioning-minimum-dte` / `--dealer-positioning-maximum-dte`: analytics contract horizon.
- `--dealer-positioning-maximum-snapshot-age-days`: defaults to `0`, requiring the just-ingested date.
- `--dealer-sign-convention`: `street_proxy`, `customer_long_proxy`, or `unsigned_market_exposure`.

## Operational behavior

Symbol-level missing chains or missing underlying prices are recorded as `SKIPPED`. Unexpected calculation or persistence errors are recorded as `FAILED`. By default, these do not roll back or invalidate the completed options ingestion. The consolidated JSON report records every symbol outcome.

## Intraday retention limitation

The raw and derived schemas identify snapshots by calendar `quote_date` / `as_of_date`, not by timestamp. Multiple same-day runs therefore maintain the latest same-day state rather than preserving every intraday version. A future intraday-history phase should add `snapshot_timestamp` to raw and derived primary keys if time-series retention inside the trading day is required.
