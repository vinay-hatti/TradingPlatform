# Milestone 44 — Institutional Market Structure & Dealer Positioning Analytics

Implemented as a governed estimator over persisted Polygon option snapshots and persisted underlying prices.

## Capabilities

- GEX, DEX, model-derived vanna and charm exposure by strike and expiration
- Gamma regime, gamma-flip/zero-gamma proxy, call wall, put wall and magnet strike
- Dealer support/resistance, expected move, ATM IV, term slope, skew and volatility risk premium
- Call/put premium-flow proxies, dealer hedging pressure, pin risk
- Institutional positioning score and bull/bear/range/breakout/volatility probabilities
- JSON, strike CSV, expiration CSV and HTML reporting
- SQLAlchemy persistence model and Alembic migration
- Root CLI command: `institutional-market-structure`

## Important interpretation

Dealer holdings are not published in the option-chain snapshot. The implementation therefore labels results as an OI/Greeks dealer-position proxy, records the sign convention, assumptions, warnings and confidence, and never represents estimated inventory as observed fact.

## Commands

```bash
uv run alembic upgrade head
uv run python scripts/test_m44_institutional_market_structure.py
uv run python -m trading_ai institutional-market-structure --symbol SPY --as-of 2026-07-24
```

Reports are written under `reports/m44/<as-of-date>/`.
