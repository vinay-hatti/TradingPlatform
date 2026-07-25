# Milestone 44 Daily Scanner Integration

The Daily Scanner now loads the latest persisted `dealer_position_snapshot` for each candidate symbol before final ranking.

## Governance

- Fresh snapshots influence ranking.
- Missing, stale, or unreadable snapshots produce a neutral adjustment.
- Default maximum age is one calendar day.
- Adjustment defaults to a maximum absolute value of 15 points.
- The original AI score is retained in `base_ai_score`.
- The final ranked score remains in `ai_score`.
- No Polygon request or Milestone 44 recalculation occurs during scanning.

## CLI

```bash
uv run python scripts/run_daily_scan.py \
  --enable-dealer-positioning \
  --dealer-positioning-max-age-days 1 \
  --dealer-positioning-weight 1.0 \
  --dealer-positioning-max-adjustment 15
```

Disable for comparison:

```bash
uv run python scripts/run_daily_scan.py --disable-dealer-positioning
```

## UI build

The Daily Scanner source page removes the **Data architecture** panel and adds dealer-positioning columns to Best Trade Candidates.

After installing the drop-in on macOS:

```bash
cd ui/workstation
npm install
npm run build
```

## Validation

```bash
uv run python scripts/test_m44_daily_scanner_integration.py
```
