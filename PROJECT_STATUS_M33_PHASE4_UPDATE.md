# Milestone 33 — Interactive Institutional Trading Workstation

## Phase 4 — Interactive Portfolio Management, Aggregated Greeks, Scenario Analysis, Exposure Heatmaps & Rebalancing

**Status:** COMPLETE

Implemented:
- paper-position normalization
- portfolio summary and P/L
- gross/net exposure
- aggregated Greeks
- symbol/expiration risk matrix
- interactive position table
- exposure heatmap
- spot/volatility/time scenario grid
- Greek-based scenario attribution
- risk-limit-driven rebalance proposal
- Phase 3 handoff metadata
- REST APIs
- regression tests
- guarded installer

Safety:
- portfolio state remains read-only
- no direct position editing
- no direct order submission
- rebalances require Phase 3 preview and four-eye approval
- live trading remains disabled

Next:
- Milestone 33 Phase 5 — Research Workbench, Interactive Scanner, Signal Explorer, Feature Importance, Walk-Forward Explorer & Trade Replay
