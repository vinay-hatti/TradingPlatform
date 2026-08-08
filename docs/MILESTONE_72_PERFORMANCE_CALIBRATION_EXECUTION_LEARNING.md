# Milestone 72 — Performance Calibration & Execution Learning

## Purpose
Close the governed learning loop across trade decisions, OPEX forecasts, and broker execution.

## Existing capabilities retained
- M65 trade-outcome reconstruction, attribution, Brier/log-loss/ECE and governed policies.
- M70 execution telemetry, fills, slippage, quality scores and learning samples.
- M71 immutable OPEX forecasts and realized 50/68/90 range/magnet/actionable outcomes.

## M72 additions
- Immutable unified prediction registry for trade decisions and OPEX forecasts.
- Prediction-to-outcome registry with idempotent realization.
- Segmented calibration by source, model version, symbol, strategy and market regime.
- OPEX coverage target errors and magnet/actionable hit tracking.
- Execution edge-preservation analytics, decision-to-submit latency and fill latency.
- Integrated Performance Command Center Outcome Learning tab.
- Automatic learning-cycle invocation from shared ingestion finalization.
- Human-governed learning only; no autonomous weight activation.

## Acceptance gates
- Prediction/outcome capture is immutable/idempotent.
- Calibration probabilities normalize 0-1/0-100 safely.
- No learning policy is activated automatically.
- Existing M65/M70/M71 APIs remain backward compatible.
- UI production build passes.
