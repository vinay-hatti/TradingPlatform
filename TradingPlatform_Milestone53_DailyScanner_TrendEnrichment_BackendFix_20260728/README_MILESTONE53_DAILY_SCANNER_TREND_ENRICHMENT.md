# Milestone 53 — Daily Scanner Trend Enrichment Backend Fix

This cumulative drop-in patch wires persisted Milestone 52 forecast and institutional trend snapshots into every Daily Scanner candidate.

## Corrected pipeline

- Loads `TrendForecastRepository` and `InstitutionalTrendRepository` in `DailyScanner`.
- Queries governed scanner contexts using the scanner market date.
- Adds forecast and institutional score adjustments to the capped combined trend adjustment.
- Propagates all fields through `DailyCandidate`, `LiveTradeCandidate`, recommender, JSON/CSV reporting, and the API payload.
- Updates the UI status badge to reflect all four trend components.
- Keeps the final reordered Market Overview page from the preceding Milestone 53 package.

## Apply

```bash
./APPLY_MILESTONE53_DAILY_SCANNER_TREND_ENRICHMENT.sh /Users/vinay.hatti/TradingPlatform
```

## Validate persisted contexts

```bash
cd /Users/vinay.hatti/TradingPlatform
uv run python scripts/verify_m53_daily_scanner_trend_context.py \
  --symbols AAPL,MSFT,AMZN \
  --signal CALL \
  --horizon-days 10 \
  --reference-date 2026-07-28
```

Every populated symbol should show `forecast_context_status: FRESH` and `institutional_context_status: FRESH`.

## Validate package contract

```bash
uv run python scripts/test_m53_daily_scanner_trend_enrichment.py
python -m py_compile \
  src/trading_ai/daily/scanner.py \
  src/trading_ai/daily/models.py \
  src/trading_ai/daily/trade_candidate.py \
  src/trading_ai/daily/recommender.py \
  src/trading_ai/daily/reporter.py
```

Then rerun the Daily Scanner. Previously generated scanner reports are immutable and will continue to contain the old fallback fields; a new scan is required.
