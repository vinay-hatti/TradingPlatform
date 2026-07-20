# Milestone 34 — Institutional Research Workstation

## Phase 2 — Candidate Analysis and Option Chain Explorer

### Step 4 — Institutional Explainability and Scenario Analysis

**Status:** COMPLETE

Implemented:

- institutional explainability package
- explainability policy
- decision-factor profile
- scenario-definition profile
- scenario-outcome profile
- scenario-comparison profile
- scenario-analysis profile
- aggregate institutional explainability profile
- weighted technical attribution
- weighted liquidity attribution
- weighted volatility attribution
- weighted institutional attribution
- weighted risk/reward attribution
- weighted payoff-efficiency attribution
- factor direction and materiality classification
- explainability score
- APPROVED, WATCH, and REJECTED classification
- default base scenario
- bullish and bearish price shocks
- volatility expansion and contraction shocks
- time-decay shock
- custom scenario support
- payoff-based scenario valuation
- Delta scenario effect
- Gamma scenario effect
- Theta scenario effect
- Vega scenario effect
- projected scenario return on risk
- scenario risk grading
- best and worst scenario comparison
- payoff range analysis
- favorable and adverse scenario counts
- high-risk scenario count
- probability-weighted scenario P/L
- primary driver selection
- primary risk selection
- decision summary
- deterministic audit narrative
- warning propagation
- JSON serialization
- report writer
- primary regression
- stress-scenario regression
- additive, backward-compatible architecture

Pending in Phase 2:

- Step 5 — Dashboard Integration, Reporting, Full Regression, and Phase Closure

## Regression correction

- corrected primary-risk attribution for adverse payoff scenarios
- negative worst-scenario P/L now surfaces Payoff Efficiency as a primary risk
- static factor direction and materiality classifications remain unchanged
- scenario-stress regression aligned with institutional explainability intent
