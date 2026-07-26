# Milestone 48 — Index Market Overview Integration

SPX, NDX, and RUT are now first-class cash-index benchmarks on the Market Overview page.

## Included surfaces

- Benchmark index context table
- Cash-index and ETF-proxy classification
- SPX/SPY, NDX/QQQ, and RUT/IWM 20-day return-spread comparison
- Cash-index trend and momentum contribution to market regime
- Index dealer-positioning and options-structure rows when snapshots exist
- Strongest and weakest cash-index opportunity context
- Cash-index data freshness

## Governance

Cash indices are explicitly excluded from:

- stock advancer/decliner breadth
- up/down-volume breadth
- relative-volume participation
- sector rotation

Their zero or absent volume is therefore never interpreted as weak participation.

The Market Overview still consumes persisted canonical symbols (`SPX`, `NDX`, `RUT`). Polygon-prefixed identifiers remain isolated inside the ingestion provider boundary.
