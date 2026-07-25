# Milestone 44 — Institutional Market Structure & Dealer Positioning Analytics

This implementation reads exclusively from the persisted `option_contract_history` snapshot and persisted `price_history`. Analytics execution makes no Polygon requests.

## Install

```bash
uv run alembic upgrade head
```

Migration `m44_002` preserves the original Milestone 44 table as `institutional_market_structure_snapshot_legacy` and creates:

- `dealer_position_snapshot`
- `dealer_strike_profile`
- `dealer_expiration_profile`
- `iv_surface_snapshot`

## Validate

```bash
uv run python scripts/test_m44_institutional_market_structure.py
uv run python scripts/test_m44_persisted_snapshot_architecture.py
```

## Run

```bash
uv run python -m trading_ai institutional-market-structure \
  --symbol SPY \
  --as-of 2026-07-24 \
  --minimum-dte 1 \
  --maximum-dte 180 \
  --maximum-snapshot-age-days 3 \
  --dealer-sign-convention street_proxy
```

Reports are written to `reports/m44/<option-snapshot-date>/` as JSON, HTML, strike CSV, expiration CSV, and IV-surface CSV.

## Governance

- `COMPUTED`: direct aggregation of persisted Polygon snapshot fields.
- `MODEL_DERIVED`: gamma flip, vanna/charm, probabilities and calibrated scores.
- `ESTIMATED`: dealer-side exposure and snapshot activity proxies.
- Dealer inventory is never represented as directly observed.
- Snapshot volume/premium is not labeled as sweeps, blocks, aggressor flow, or opening/closing transactions.
