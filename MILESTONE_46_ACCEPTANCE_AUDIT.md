# Milestone 46 Acceptance Audit

Baseline: `TradingPlatform(7).zip`
Calculation version: `m46.1`

| Criterion | Status | Evidence / limitation |
|---|---|---|
| AC-1 True correlation analytics | PASS | Rolling 60-session pairwise matrix, average/median correlation, sector correlations, dispersion and governed regimes persisted in correlation tables. |
| AC-2 Internal sentiment ensemble | PASS | Fourteen independently weighted components with score, direction, confidence, contribution and provenance. |
| AC-3 Governed sector registry | PASS | Effective-dated `sector_membership` seeded from the canonical universe, with source, confidence and verification timestamp. Industry/sub-industry remain nullable because the canonical file does not provide them. |
| AC-4 Constituent sector breadth | PASS | Constituent-level EMA/SMA/MACD/RSI, advances, volume, highs/lows, equal-weight returns and rotation labels. |
| AC-5 Enhanced dealer ensemble | PASS | OI/Greeks exposure, confidence, positioning changes, GEX/DEX/Vanna/Charm changes, wall/flip migration and conviction. Always marked `ESTIMATED`. |
| AC-6 Historical options snapshots | PARTIAL | Derived Milestone 46 snapshots preserve intraday timestamps. The attached raw `option_contract_history` and Milestone 44 tables remain date-keyed and therefore cannot reconstruct multiple same-day raw captures. A future schema migration must add raw `snapshot_timestamp` and revise conflict keys. |
| AC-7 Market internals | PASS | A/D, volume breadth, TRIN, McClellan oscillator/summation, Zweig breadth thrust and cumulative breadth. Exchange TICK is correctly `DATA_BLOCKED`. |
| AC-8 Expanded volatility analytics | PARTIAL | Existing Milestone 45 persisted volatility/options structure is surfaced and governed. Full historical IV-rank/percentile and VIX-futures term structure require timestamped raw options/VIX futures history. |
| AC-9 Institutional liquidity analytics | PARTIAL | Existing persisted equity participation and options quote coverage are consumed. Order-book depth and average trade size are `DATA_BLOCKED`; historical intraday liquidity trend needs AC-6 raw timestamps. |
| AC-10 Comprehensive risk dashboard | PASS | Twelve decomposed risks, aggregate score/regime and evidence-based alerts. |
| AC-11 Opportunity dashboard | PASS | Ranked sector and dealer-alignment opportunities with direction, strategy, confidence and factors. |
| AC-12 Market Overview UI | PASS | Correlation, sentiment components, constituent sector breadth, market internals, risk components, dealer migration and opportunities added. Existing volatility/liquidity/cross-asset panels retained. |
| AC-13 Daily Scanner integration | PASS | Separate market, sector and risk adjustments; neutral missing-data behavior; reasons appended to ranking explanation. |
| AC-14 Institutional Decision integration | PARTIAL | Candidate objects and serialized scanner artifacts carry the full new context. A dedicated decision-engine policy consumer was not present in the attached Milestone 45 path and requires a subsequent decision-engine wiring step. |
| AC-15 Persistence and API | PASS | Normalized tables plus latest/refresh/scanner/correlation/sectors/dealer/risk/opportunity endpoints. |
| AC-16 Ingestion orchestration | PASS | Market Intelligence runs after Market Overview and is non-blocking; `--skip-market-intelligence` is supported. |
| AC-17 Governance and provenance | PASS | Source tables, model version, computed/model-derived/estimated classes, confidence and explicit warnings are carried in snapshots. |
| AC-18 Tests and audit | PASS | Engine math/behavior, integration contracts, M44/M45 regressions, Python compilation and TypeScript type checking passed. |

## Data-blocked facts

1. True dealer inventory is not publicly observable. All dealer outputs remain estimated.
2. Exchange TICK requires an authoritative exchange-level intraday tick feed.
3. Order-book depth and average trade size require trade/quote microstructure data.
4. Same-day raw options history requires a migration of the raw option and Milestone 44 keys to include `snapshot_timestamp`.

## Regression results

```text
Milestone 46 market intelligence assertions passed.
Milestone 46 integration contract assertions passed.
Milestone 45 market overview contract assertions passed.
Milestone 45 Market Overview UI and persistence assertions passed.
Milestone 44 daily scanner dealer-positioning assertions passed.
Python compileall passed.
TypeScript tsc --noEmit passed.
```
