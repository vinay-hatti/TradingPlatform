# Milestone 33 — Interactive Institutional Trading Workstation

## Phase 3 — Professional Order Entry, Multi-Leg Strategy Builder, Position Sizing, Margin Preview & Approval Workflow

**Status:** COMPLETE

Implemented:
- multi-leg option strategy tickets
- strategy classification
- net debit/credit preview
- commission estimate
- margin estimate
- maximum loss/profit where determinable
- breakeven estimates
- aggregate Greeks
- account risk-budget sizing
- recommended contract count
- bounded/unbounded risk warnings
- persisted approval queue
- four-eye approval enforcement
- confirmation-token validation
- permission validation
- governed paper-leg submission
- partial-submission status and errors
- REST APIs
- interactive workstation page
- regression tests
- guarded installer

Safety:
- live trading remains disabled
- requester cannot approve own ticket
- submission requires prior approval
- every leg is submitted through existing paper governance

Next:
- Milestone 33 Phase 4 — Interactive Portfolio Management, Aggregated Greeks, Scenario Analysis, Exposure Heatmaps & Rebalancing
