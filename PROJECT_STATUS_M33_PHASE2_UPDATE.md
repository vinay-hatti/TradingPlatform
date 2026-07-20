# Milestone 33 — Interactive Institutional Trading Workstation

## Phase 2 — Institutional Option Chain, Live Greeks, Liquidity Ladder & Volatility Visualization

**Status:** COMPLETE

Implemented:

- institutional option-chain domain models
- option-chain query contract
- stored option-chain repository access
- latest quote-date discovery
- expiration discovery
- underlying-price resolution
- provider Greek support
- Black–Scholes Greek fallback
- Greek-source attribution
- implied-volatility normalization
- midpoint and spread analytics
- spread-percentage filtering
- volume filtering
- open-interest filtering
- strike filtering
- option-type filtering
- intrinsic value
- extrinsic value
- moneyness
- liquidity score
- quote-quality classification
- put/call volume ratio
- put/call open-interest ratio
- volatility smile
- liquidity ladder
- institutional call/put chain table
- selected-contract handoff to paper order entry
- REST APIs
- regression tests
- guarded installer
- backward-compatible workstation navigation

Safety:

- no order is submitted from the option-chain page
- contract selection opens the governed paper-order workflow
- live broker routing remains disabled
- delayed/stored data is labeled as delayed

Next:

- Milestone 33 Phase 3 — Professional Order Entry,
  Multi-Leg Strategy Builder, Sizing, Margin Preview & Approval Workflow
