# Milestone 53 — Forecast Horizon Candidate Propagation Fix

Corrects `DailyCandidate.__init__()` failures caused by new forecast-horizon provenance fields returned by `TrendForecastRepository.scanner_context()`.

Includes cumulative nearest-horizon repository behavior and propagates requested/resolved horizon metadata through DailyCandidate, LiveTradeCandidate, recommender, reporter, and ranking explanation.

Apply, then run:

```bash
uv run python scripts/test_m53_forecast_horizon_candidate_propagation.py
```
