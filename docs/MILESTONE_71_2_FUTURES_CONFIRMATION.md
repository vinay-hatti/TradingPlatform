# Milestone 71.2 — Institutional OPEX Forecast & Futures Confirmation

Binding scope:
- Polygon/Massive futures provider for ES, NQ, RTY.
- Automatic active-contract discovery and roll lineage.
- Raw 1-minute and session OHLCV persistence.
- Futures trend, momentum, VWAP, overnight/RTH structure, realized volatility and cash/futures basis.
- Dealer-vs-futures interaction classification (confirmed, absorbed, overridden, mixed).
- Futures evidence in OPEX scenario posterior and confidence decomposition.
- Market-impact-weighted event uncertainty so thousands of single-stock earnings do not dominate index forecasts.
- Staged near-path objectives; extreme 90% tails remain separate from actionable ranges.
- Existing M71/M71.1 OPEX persistence and UI remain additive/backward compatible.

Provider note: Polygon rebranded to Massive; current official futures REST documentation uses https://api.massive.com/futures/v1. `POLYGON_FUTURES_BASE_URL` remains configurable.
