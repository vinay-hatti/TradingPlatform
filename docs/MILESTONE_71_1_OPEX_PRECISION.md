# Milestone 71.1 — OPEX Forecast Precision & Conditional Path Intelligence

M71.1 strengthens the M71 probabilistic OPEX framework without pretending uncertainty is smaller than the data supports.

## Additions

- Expiration-specific option-surface risk-neutral density from persisted IV surface snapshots using a smoothed Breeden–Litzenberger finite-difference estimator.
- Separate unconditional, model-calibrated and dominant-scenario actionable ranges.
- Historical OPEX analogs from underlying price history, matched on realized volatility and momentum.
- Bayesian/posterior continuity using the prior intraday forecast when current evidence agrees.
- Explicit range-width attribution: option-implied volatility, realized volatility, event uncertainty, dealer-position uncertainty, trend/path uncertainty and calibration uncertainty.
- Magnet-zone probability in addition to exact-strike magnet probability.
- Barrier touch, first-touch, hold and break probabilities for support, resistance, magnet, gamma flip and wall levels.
- Event-conditioned base/bullish/bearish distributions.
- Expiration-specific structural dealer positioning versus 0DTE/near-term tactical positioning.
- OI-change plus intraday-volume inference for likely opening/closing/roll-like positioning changes.
- SPX/NDX/RUT cross-index confirmation plus Market Overview breadth context.
- Cross-OPEX map upgraded with calibrated 68% range, actionable range and magnet-zone probability migration.
- Outcome calibration extended for actionable-range and magnet-zone hit rates.

## Governance

The actionable range is explicitly conditional on the dominant scenario and is not labeled as a 50/68/90% unconditional coverage interval. Dealer positioning remains an OI-and-Greeks estimator, not observed dealer inventory. Opening/closing classification is inference and carries an explicit confidence score. Surface-derived distributions are only used when the persisted surface passes minimum convexity/data-quality checks; otherwise the engine retains governed fallbacks.

## Persistence

No new database migration is required. M71.1 fields are additive inside the existing `opex_forecast_snapshots.payload_json` and `opex_forecast_outcomes.payload_json` contracts introduced by `m71_001`.
