Yes. I went through the current source baseline plus the cumulative changes we have applied through `.15.7`, and the options ingestion path today is much more than “download option chains.” It is effectively the **options-side orchestration engine for a large part of the institutional decision pipeline**.

At a high level, the scheduled production flow is now:

```text
HOURLY GOVERNED CYCLE
        ↓
Underlying ingestion
        ↓
Trend / Forecast / Institutional Participation
        ↓
Market Intelligence
        ↓
Stock Intelligence
        ↓
Inflection Intelligence — underlying-primary
        ↓
M62 opportunity materialization
        ↓
Capture exact Stock Intelligence run_id
        ↓
OPTIONS INGESTION
        ↓
Raw Polygon chain capture
        ↓
Validation / deduplication / persistence
        ↓
Governed option snapshot publication
        ↓
Volatility snapshots
        ↓
Liquidity snapshots
        ↓
Dealer positioning
        ↓
Market Overview refresh
        ↓
Market Intelligence refresh
        ↓
Market-state publication
        ↓
Reuse exact underlying-owned Stock Intelligence authority
        ↓
Inflection Intelligence — options enrichment
        ↓
M62 strategy generation
        ↓
Exact contract optimization
        ↓
Option Valuation Intelligence
        ↓
Strategy valuation / dynamic management
        ↓
Trade-plan certification
        ↓
Institutional Decision snapshots
        ↓
Advancement authority publication
        ↓
Futures Intelligence attempt
        ↓
OPEX Intelligence
        ↓
Continuous Learning
        ↓
Exact Stock-lineage verification
```

That is what `ingest_options_data.py` actually means today.

## 1. What the scheduled production job asks it to ingest

The current hourly orchestration calls options ingestion with:

```text
Universe:
    canonical equities
    ETFs
    indexes

DTE:
    1 → 180 days

Minimum OI:
    1

Minimum volume:
    0

Maximum strike distance:
    ±40% from underlying

Polygon rate:
    8 requests/sec

Persistence batch:
    10,000 records

Institutional Options:
    REQUIRED

Shared finalization:
    REQUIRED
```

One important point: the hourly command does **not** use `--force-options-refresh`.

That does **not** mean it reuses old options.

Fresh Polygon options are the normal default. `--reuse-options-snapshot` is the explicit option needed to avoid Polygon requests.

`--force-options-refresh` primarily means:

> reset the ingestion manifest and rebuild instead of allowing resume semantics.

So every normal hourly production run still requests a **fresh Polygon chain**.

---

# 2. Canonical-universe resolution

Before calling Polygon, it resolves the canonical universe from:

```text
data/universe/us_listed_equities_etfs.csv
data/universe/us_market_indices.csv
```

It creates normalized instrument objects and only sends instruments marked:

```text
options_eligible = true
```

For index instruments it preserves separate identities such as:

```text
SPX
  canonical            SPX
  price ticker         I:SPX
  option snapshot      I:SPX
  option reference     SPX
```

This is good architecture because vendor symbols are kept separate from platform identity.

---

# 3. Fresh option-cycle identity

Every fresh run gets its own governed cycle ID similar to:

```text
options-20260817T....
```

That ID becomes important throughout the rest of the pipeline.

It is not merely a logging token. It ultimately becomes the lineage identifier attached to the timestamped option snapshot and downstream intelligence.

The run manifest records:

```text
capture date
minimum DTE
maximum DTE
symbol count
mode
valid records
persisted records
failed batches
governed snapshot ID
governed snapshot timestamp
completion status
```

This allows interrupted runs to resume batch-by-batch.

---

# 4. Polygon option-chain acquisition

The provider is exclusively:

```text
Polygon /v3/snapshot/options/{underlying}
```

For each symbol it requests:

```text
expiration_date >= today + minimum_dte
expiration_date <= today + maximum_dte
limit = 250 per Polygon page
sort = expiration_date
ascending
```

It follows every Polygon `next_url` until the chain has been exhausted.

### Throttling

It enforces the configured request rate:

```text
8 requests/sec in the scheduled run
```

The provider itself defaults to 4/s, but the production scheduler overrides it to 8.

### Retry behavior

Retryable failures include:

```text
HTTP 429
HTTP 5xx
network/request exceptions
invalid JSON response
```

It will attempt each request up to six times with exponential backoff and jitter.

The built-in retry delays grow from approximately:

```text
1 sec
2 sec
4 sec
8 sec
16 sec
30 sec cap
```

That is separate from the higher-level ingestion batch resume mechanism.

---

# 5. What is captured from Polygon

Each Polygon option contract is normalized into the internal `OptionQuoteRecord`.

Identity:

```text
underlying
expiration
strike
CALL / PUT
Polygon option ticker
```

Market data:

```text
bid
ask
last trade
volume
open interest
implied volatility
```

Greeks:

```text
delta
gamma
theta
vega
```

Additional provenance:

```text
underlying price supplied by Polygon
provider quote timestamp
break-even price
source = polygon_option_chain_snapshot
```

The timestamp handling is reasonably defensive: it understands Polygon timestamps supplied in nanoseconds and lower precisions and normalizes them to UTC ISO timestamps.

---

# 6. Provider-level filtering

Before a contract even reaches the formal validation engine, the Polygon provider filters it.

Current scheduled thresholds are:

```text
DTE               1–180
OI                 >= 1
Volume             >= 0
Strike distance    <= 40% from spot
```

So a contract outside that scope is simply excluded from the captured dataset.

This matters conceptually:

**the raw Polygon chain and the persisted platform chain are not identical.**

The platform deliberately captures a governed, relevant subset.

---

# 7. Mapping failures

Malformed Polygon records are also excluded if the mapper cannot construct a valid contract because of something such as:

```text
missing expiration
missing strike
unrecognized option type
invalid numeric values
```

There is a weakness here that I would put on our improvement list:

**these mapper-level drops are currently silently skipped.**

They don't become formal validation rejections and therefore don't appear prominently in the ingestion metrics.

That means:

```text
Polygon returned 100 records
mapper silently skipped 2
validation evaluated 98
```

can look like 98 records were simply the source population.

I would eventually add explicit:

```text
provider_records_received
mapping_rejected
policy_filtered
validation_rejected
persisted
```

so coverage is fully explainable.

---

# 8. Batching

Accepted provider records are accumulated into batches.

The current scheduled batch size is:

```text
10,000
```

Batch identity is deterministic:

```text
polygon:<date>:<symbol>:<page>
```

Example conceptually:

```text
polygon:2026-08-17:AAPL:1
polygon:2026-08-17:AAPL:2
```

This is what enables resumable ingestion.

---

# 9. Batch resume / manifest governance

Before processing a batch, the service checks:

```text
Has this batch already completed in this cycle?
```

If yes:

```text
skip it
increment resumed_batches
```

Otherwise the batch goes through the data-quality pipeline.

That gives us safe restart semantics for a large chain ingest instead of restarting hundreds of thousands of contracts.

---

# 10. Deduplication

The first data-quality stage is:

```text
OptionContractDeduplicator
```

Duplicate contract observations inside a provider batch are collapsed before validation/persistence.

The skipped duplicates contribute to the batch's `skipped_records`.

---

# 11. Formal option-contract validation

Every surviving record goes through `OptionContractValidationEngine`.

It validates four broad domains.

### Identity

Checks include:

```text
non-empty underlying
strike within configured bounds
contract not expired
DTE within validation-policy bounds
```

### Market values

Checks:

```text
bid finite
ask finite
last finite

bid >= 0
ask >= 0
last >= 0

bid <= ask
```

A crossed market is an ERROR.

Wide spreads are usually a WARNING rather than automatically invalidating the raw record.

### Implied volatility

Checks:

```text
IV finite
IV >= 0
```

Extreme IV becomes a warning according to policy rather than automatically destroying the contract.

### Liquidity data

Checks that:

```text
volume >= 0
open interest >= 0
```

when present.

### Greeks

Checks:

```text
delta within [-1,+1]
gamma within policy range
vega within policy range
theta within policy range
```

It also flags unusual semantic combinations such as:

```text
negative call delta
positive put delta
```

as warnings.

Only records with no ERROR severity make it into persistence.

---

# 12. Persistence into `option_contract_history`

Validated contracts are persisted to:

```text
option_contract_history
```

Fields include:

```text
underlying_symbol
option_symbol
quote_date
quote_timestamp

expiry
option_type
strike

bid
ask
last

volume
open_interest

implied_volatility

delta
gamma
theta
vega

source_underlying_price
```

On PostgreSQL this uses an upsert.

The preferred uniqueness identity is effectively:

```text
option_symbol + quote_date
```

when that constraint exists.

That has an important consequence.

### `option_contract_history` is daily-current, not hourly immutable history

During several hourly ingestions on the same day, the same:

```text
option_symbol + quote_date
```

row is updated.

So this table represents:

> the most recently captured value for that option contract on that trading date.

It does **not** keep every hourly revision.

That is intentional because the next layer provides true timestamped history.

---

# 13. One observability quirk in persistence

For PostgreSQL upserts, the writer currently reports all successful upserted records through:

```text
inserted_records = len(records)
updated_records = 0
```

even when many were conflict updates.

That's why our runtime output correctly calls it:

```text
persisted/upserted
```

rather than claiming they are literally new inserts.

I would not treat this as a trading defect, but the metrics could be improved. We could distinguish:

```text
new contracts
same-day updates
unchanged rows
```

much more accurately.

---

# 14. Governed option snapshot publication

Raw compatibility persistence is **not sufficient** to let downstream intelligence proceed.

After the raw ingestion completes successfully, `_publish_fresh_option_lineage()` runs.

This converts the current daily contract rows into immutable timestamped governed snapshots.

It creates:

```text
option_snapshot_run
```

and:

```text
option_contract_snapshot
```

The snapshot contains the exact capture timestamp.

So the architecture is:

```text
option_contract_history
    latest daily compatibility representation

             ↓

option_snapshot_run
option_contract_snapshot
    timestamped governed historical lineage
```

That is a good separation.

---

# 15. Snapshot completeness

The publisher asks:

> Of all requested options-eligible symbols, how many actually produced persisted option rows?

It calculates:

```text
completeness_score =
symbols_with_contracts / symbols_requested × 100
```

and marks the run:

```text
READY
```

or:

```text
PARTIAL
```

The snapshot run records:

```text
symbols requested
symbols succeeded
symbols failed
contracts received
contracts persisted
warnings
capture status
partial flag
completeness score
```

If **zero governed option rows** are generated, downstream publication is blocked.

---

# 16. Quote-quality classification

Every timestamped contract snapshot is also classified as:

```text
COMPLETE_QUOTE
ONE_SIDED_QUOTE
NO_QUOTE
```

based on bid/ask availability.

A `mark` is calculated from:

1. stored midpoint if available,
2. `(bid + ask)/2`,
3. otherwise last price.

That becomes important in later valuation and liquidity calculations.

---

# 17. Underlying volatility intelligence

Immediately after creating the governed contract snapshot, the pipeline builds:

```text
underlying_volatility_snapshot
```

for every symbol.

It searches the snapshot for liquid near-30-DTE contracts and derives an approximate:

```text
ATM IV 30d
```

The contract selection favors:

```text
DTE close to 30
absolute delta close to 0.50
positive IV
valid bid/ask
```

using up to roughly 12 near-ATM observations.

It then calculates:

```text
ATM IV
20-day realized volatility
IV Rank
IV Percentile
Volatility Risk Premium = IV - realized vol
strategy-fit regime
confidence
```

IV Rank and Percentile use up to 252 previous volatility observations.

This is one reason hourly option ingestion now matters well beyond contract prices—it continually updates the volatility context used elsewhere.

---

# 18. Microstructure liquidity intelligence

The same governed option snapshot produces:

```text
microstructure_liquidity_snapshot
```

for each symbol.

It derives measures including:

```text
percentage of executable quotes
median relative bid/ask spread
liquidity score
liquidity regime
confidence
```

The implementation explicitly records that true exchange depth is unavailable:

```text
depth_available = false
depth_status = CAPABILITY_UNAVAILABLE
```

and trade-size metrics are not captured by this particular snapshot endpoint.

That is good governance—the system does not pretend Polygon snapshot data gives us a true full order book.

---

# 19. Fresh-lineage gate

Both volatility and liquidity snapshot creation are mandatory for a healthy fresh lineage.

If either produces zero rows:

```text
downstream publication is blocked
```

So the platform refuses to say:

> “fresh options are ready”

if only raw contract rows were written but derived intelligence couldn't be built.

---

# 20. Dealer Positioning refresh

After a successful fresh option snapshot, dealer positioning runs.

Even though the scheduled command does not explicitly say:

```text
--force-dealer-refresh
```

the options wrapper does this internally:

```text
if options_refreshed:
    force_dealer_refresh = True
```

So **every successful fresh hourly Polygon capture also refreshes dealer positioning**.

That is important.

---

# 21. Dealer Positioning consumes much more than GEX

The current dealer subsystem calculates and persists things including:

```text
unsigned gamma exposure
net gamma exposure

unsigned delta exposure
net delta exposure

net vanna exposure
net charm exposure
```

plus structural information:

```text
gamma regime
gamma flip
gamma-flip distance
gamma-flip confidence

primary call wall
secondary call wall

primary put wall
secondary put wall

magnet strike
```

and volatility structure:

```text
expected move
expected move %
ATM IV
IV term slope
put skew
call skew
```

It also derives:

```text
institutional positioning score
positioning label

bull probability
bear probability
range probability
breakout probability
breakdown probability

volatility-expansion probability
volatility-compression probability
```

plus confidence and warnings.

There are strike-level and expiration-level persisted exposure profiles as well.

So the dealer stage is an actual **market-structure intelligence engine**, not just a GEX chart.

---

# 22. Market Overview gets refreshed again

After options and dealer positioning finish, the shared finalizer runs.

Because:

```text
upstream_refreshed = options_refreshed OR dealer_refreshed
```

Market Overview recognizes that new information has arrived.

It recalculates the market-wide state using the newly available option/dealer context.

This is why an options-only run can change:

```text
market health
breadth
bias
volatility environment
dealer context
risk state
```

even though underlying prices may not have changed much.

---

# 23. Market Intelligence is recalculated

Next:

```text
Market Intelligence
```

is refreshed.

This updates higher-level signals such as:

```text
correlation regime
sentiment
risk
cross-asset / market regime context
```

depending on current available data.

Then the current market state is republished.

---

# 24. Stock Intelligence is NOT rebuilt during options ingestion

This distinction is critical.

Today, because of `.15.6`, **underlying ingestion owns Stock Intelligence authority**.

During options finalization the code explicitly does:

```text
reuse latest underlying-owned materialized Stock Intelligence publication
```

It does **not** create another stock scanner run.

That was one of the lineage problems we fixed.

The options phase therefore says conceptually:

> “Enrich this exact underlying decision population with current options evidence.”

not:

> “create a new underlying population.”

---

# 25. Exact lineage requirement

The current scheduled job captures the Stock Intelligence `run_id` after underlying completes.

For example:

```text
stock-scan-XYZ
```

Then options must process that same authority.

After options completes, the scheduler runs:

```text
verify_intraday_ingestion_lineage.py
```

and checks:

```text
expected Stock run ID
        ==
actual current Stock run ID
        ==
Institutional Options opportunity lineage
```

Mismatch:

```text
FAIL CLOSED
```

This is now one of the strongest governance protections in the pipeline.

---

# 26. Inflection Intelligence is run a second time

The options phase runs Inflection Intelligence in:

```text
OPTIONS_ENRICHMENT
```

mode.

Underlying ingestion previously ran:

```text
UNDERLYING_PRIMARY
```

So conceptually:

```text
first pass
price/trend/participation/structure-based inflection

second pass
same underlying authority enriched by options/dealer/volatility evidence
```

This is exactly where the architecture starts becoming truly multi-domain rather than merely technical-analysis driven.

---

# 27. Institutional Options does NOT create opportunities here

Opportunity creation belongs to underlying ingestion.

During options ingestion:

```text
Institutional Options materialization:
NOT EXECUTED
```

That is deliberate.

It instead loads the opportunity IDs associated with the current exact:

```text
current_stock_intelligence
```

publication.

Those are the only opportunities the downstream options pipeline is allowed to advance.

---

# 28. Advancement authority is invalidated before a full refresh

When all four major downstream stages are enabled:

```text
strategy generation
contract optimization
option valuation
decisions
```

the existing advancement authority for the Stock run is first invalidated with:

```text
FULL_OPTIONS_ADVANCEMENT_STARTED
```

This is a good fail-closed design.

It prevents yesterday's or the previous hour's complete options authority from remaining silently active while today's refresh is half finished.

---

# 29. Strategy generation

The current Institutional Options strategy catalog includes:

```text
LONG_CALL
BULL_CALL_SPREAD
BULL_PUT_SPREAD
CALL_DIAGONAL
CALL_CALENDAR

LONG_PUT
BEAR_PUT_SPREAD
BEAR_CALL_SPREAD
PUT_DIAGONAL
PUT_CALENDAR
```

Each strategy is scored against several domains:

```text
underlying thesis direction
market regime
trend regime / maturity
setup type
volatility environment
dealer positioning
complexity
probability / confidence
```

Strategies receive dispositions such as:

```text
ELIGIBLE
SELECTED
REJECTED
CONDITIONAL
```

---

# 30. `.15.5` contradictory-evidence governance is active here

This is where our recent INTC/GLD work now matters.

An opportunity is no longer only:

```text
BULLISH
or
BEARISH
```

The options strategy layer also receives a contradiction authority such as:

```text
BULLISH_CONTINUATION
BULLISH_DETERIORATING
REVERSAL_WATCH
...
```

If the dominant trend is bullish but deterioration is significant:

```text
bullish execution may be blocked
```

while the opposite-direction bearish strategy can be retained as:

```text
CONDITIONAL
```

but **not executable** until reversal confirmation occurs.

This logic now runs every hourly options refresh.

---

# 31. Exact Polygon contract optimization

For strategies that survive strategy governance, M62 moves to the actual Polygon contracts.

The contract optimizer has a narrower trading policy than raw ingestion.

Raw ingestion currently captures:

```text
DTE 1–180
```

but optimization defaults to roughly:

```text
minimum DTE      14
maximum DTE      120
target DTE       45
near DTE         30
far DTE          75

minimum OI       1
minimum volume   0
maximum spread   35%
```

That's a healthy separation:

```text
capture broadly
trade more selectively
```

---

# 32. Underlying price used by contract optimization

Contract optimization pulls:

```text
latest Polygon quote_date for symbol
```

and the underlying price from:

```text
price_history <= quote_date
```

This is exactly why we hardened hourly orchestration to run underlying first.

Otherwise contract optimization could have been matching:

```text
fresh options
against
stale underlying
```

which is no longer acceptable.

---

# 33. Implied-volatility normalization

Contract optimization has an additional IV-quality layer.

It computes a credible chain median from IVs approximately within:

```text
3% → 300%
```

If a contract has missing IV:

```text
MISSING_CHAIN_MEDIAN_FALLBACK
```

If an IV is anomalous relative to the local chain:

```text
ANOMALOUS_CHAIN_MEDIAN_FALLBACK
```

Otherwise:

```text
SOURCE
```

So a missing IV doesn't silently become the old dangerous 1% pricing floor.

This is another significant hardening already present.

---

# 34. Contract executability filtering

Candidate contracts must survive things including:

```text
valid option type
finite prices/Greeks
valid DTE
minimum OI
minimum volume
ask > 0
spread <= 35%
valid Polygon option symbol
```

Then strategy-specific exact packages are constructed.

Examples:

### Long call / put

One exact option leg.

### Vertical spread

Two same-expiration legs with strategy-appropriate strike relationships.

### Diagonal/calendar

Two distinct expirations with the appropriate near/far relationship.

The `.15.7` Trade Builder fix now agrees with this topology downstream.

---

# 35. Global strategy + contract optimization

This is an especially important M68 enhancement.

The optimizer does **not** simply:

```text
choose strategy #1
then find a contract for it
```

anymore.

It evaluates executable packages across **all eligible strategies** and ranks the combined package.

The objective combines:

```text
65% strategy quality
35% contract quality
```

with additional deterministic ordering using:

```text
executability
package score
contract score
liquidity
slippage
strategy rank
```

Then it chooses the best **globally feasible package**.

This prevents:

> “best theoretical strategy has no good contracts, but system ignores a slightly lower-ranked strategy with excellent contracts.”

That is a substantial institutional improvement.

---

# 36. Option Valuation Intelligence

After exact contracts are selected, M69 valuation runs.

This is not the same as the M62 strategy valuation later in the decision stage.

M69 asks:

> “Is this exact option package attractively or unattractively priced relative to our model?”

It only processes:

```text
executable contract recommendations
```

from the **current run**.

Historical executable flags are treated as audit history, not current authority.

Only the latest recommendation per exact:

```text
opportunity + strategy
```

lineage is valued.

---

# 37. Coherent-market-input gate

Before valuation, every package has to pass:

```text
CURRENT_COHERENT
```

market-input validation.

If underlying price, option snapshot, or other required market lineage isn't coherent:

```text
valuation_actionable = false
trade_execution_authority = false
```

and the contract is excluded from actionable valuation.

This is another fail-closed boundary.

---

# 38. Option valuation domains

The valuation engine currently combines a large set of domains:

### Implied volatility

Current leg-weighted IV.

### Realized volatility

Recent realized-vol input.

### Forecast volatility

Forward/forecast volatility when available.

### Volatility surface

Compares each package to sibling recommendations / neighboring IV structure.

### Relative value

Peer/sector implied-volatility relationships.

### Event pricing

Active governed event intelligence.

### Dealer flow

Current institutional/dealer positioning.

### Inflection Intelligence

Exact-current inflection state when lineage matches.

### Liquidity/execution

Package natural spread and modeled slippage.

This is essentially the Option Valuation & Relative Value Intelligence concept we wanted to build.

---

# 39. Fair-value model

At the leg level, the current implementation uses Black-Scholes-style option valuation with:

```text
underlying price
strike
DTE
risk-free rate
dividend yield
market IV
model forecast volatility
```

For multi-leg structures it values each leg individually using its own:

```text
strike
right
DTE
quantity
side
```

and then combines them into the package.

That is especially important for calendars and diagonals because near and far legs are not incorrectly forced to the same DTE.

---

# 40. Natural package pricing

For a fully quoted multi-leg strategy, it calculates:

```text
buy natural
sell natural
mid
package spread
```

using correct long/short leg signs.

That means debit and credit packages retain their economic sign rather than all being treated like positive option prices.

It then models expected slippage as a function of:

```text
package spread
liquidity score
```

and produces an **executable fair value**, not only a theoretical fair value.

---

# 41. Mispricing classification

The package receives a mispricing percentage and classification:

```text
STRONG_UNDERPRICED
MODERATELY_UNDERPRICED
FAIR_VALUE
MODERATELY_OVERPRICED
STRONG_OVERPRICED
```

Current thresholds are approximately:

```text
moderate edge = ±4%
strong edge   = ±12%
```

It also generates:

```text
edge score
confidence
stability index
expected persistence
fair-value range
```

---

# 42. Explainability ledger

Valuation records component attribution such as:

```text
model valuation edge
volatility edge
surface edge
relative-value edge
event edge
dealer-flow edge
inflection edge
execution/liquidity edge
```

It also records:

```text
evidence
conflicting evidence
missing/fallback domains
invalidation conditions
```

That is important because the valuation result is not just a number.

---

# 43. Relative-value snapshots

When enough peer context exists, it persists a dedicated:

```text
OptionRelativeValueSnapshot
```

including:

```text
symbol IV
peer median IV
divergence %
z-score
relationship regime
peer group
sector
```

This is cross-sectional option relative-value intelligence.

---

# 44. Decision stage runs another valuation layer

After M69 option valuation, `InstitutionalDecisionService` runs.

For opportunities in:

```text
CONTRACTS_OPTIMIZED
```

it first invokes:

```text
InstitutionalStrategyValuationService
```

This is the actual trade economics / probability valuation layer used by the decision process.

It produces things such as:

```text
calibrated probability
expected value
capital required
return on risk
trade economics
```

This is where `.15.5`'s absolute quality floor now applies.

Being rank #1 is not enough if the economics are unacceptable.

---

# 45. Dynamic management plan generation

The same decision stage generates:

```text
InstitutionalDynamicManagementService
```

artifacts.

That creates the future position-management framework:

```text
underlying structural stop
targets
trailing rules
theta rules
volatility rules
assignment/expiration rules
management activation
```

and associated execution recommendation.

This is why a recommendation reaching READY is no longer just:

> “buy this contract.”

It carries an entire governed lifecycle plan.

---

# 46. Trade-plan certification

The generated plan then has to pass Trade Plan Certification.

This checks things such as:

```text
entry geometry
stop geometry
target geometry
strategy topology
contract validity
management completeness
entry conditions
```

A certified plan can still have a disposition such as:

```text
WAITING_FOR_ENTRY
REGENERATE_REQUIRED
```

instead of immediate execution.

That distinction is precisely what `.15.4` hardened.

---

# 47. READY reconciliation

Even if an opportunity already says:

```text
READY_FOR_EXECUTION
```

the decision service does **not trust the label by itself**.

It checks the complete exact chain:

```text
current selected strategy
current exact contracts
valuation
management
execution recommendation
final certification
```

If anything is missing or stale, it pushes the opportunity back to:

```text
CONTRACTS_OPTIMIZED
```

for governed repair.

That is one of the reasons the pipeline now behaves much better after interrupted refreshes.

---

# 48. Institutional Decision Snapshot

When the complete chain is valid, it produces or refreshes the authoritative decision snapshot containing:

```text
opportunity
selected strategy
contract recommendation
valuation
execution recommendation
management plan

institutional score
calibrated probability
expected value
capital required
policy version
state hash
```

It is deterministic and idempotent: existing decisions are refreshed rather than blindly duplicated.

---

# 49. Governed non-ready outcomes

A candidate that remains in `CONTRACTS_OPTIMIZED` after decision processing is not automatically treated as an error.

If certification says:

```text
PASS
+
WAITING_FOR_ENTRY
```

or:

```text
PASS
+
REGENERATE_REQUIRED
```

it becomes:

```text
governed_not_ready
```

rather than an unexpected failure.

That distinction is critical.

It lets the hourly pipeline be healthy even though many trades are deliberately not executable.

---

# 50. Advancement result classification

The workflow distinguishes:

```text
GOVERNED_NO_STRATEGY
GOVERNED_NO_CONTRACT
MISSING_OPTION_DATA
GOVERNED_NOT_READY
RECONCILED_READY
UNEXPECTED_FAILURE
```

This is much better than treating every non-READY trade as an ingestion failure.

Overall status becomes:

```text
READY
    no governance gaps

DEGRADED
    expected governed no-trade / non-ready population exists

FAILED
    unexpected processing/system failures occurred
```

---

# 51. Advancement authority publication

If the full:

```text
strategy
contracts
valuation
decision
```

cycle completes without unexpected failures, the system persists a new **advancement authority** for that Stock Intelligence run.

If unexpected failures exist:

```text
authority = NOT_PUBLISHED
```

The old authority was invalidated at the beginning, so an incomplete cycle cannot masquerade as current.

This is exactly how a governed institutional pipeline should behave.

---

# 52. Futures Intelligence is also invoked

After the main options work, shared finalization tries to refresh:

```text
ES
NQ
RTY
```

futures intelligence.

In your recent runs this has been failing because the futures provider looks for:

```text
POLYGON_API_KEY
or MASSIVE_API_KEY
```

in its own environment path.

That failure is currently:

```text
required=False
```

so it does **not fail options ingestion**.

This is a legitimate degraded ancillary domain rather than a blocker.

We should eventually resolve that environment inconsistency.

---

# 53. OPEX Intelligence

Next:

```text
OPEX Intelligence
```

is refreshed for:

```text
SPX
NDX
RUT
```

across three cycles.

It uses the newly refreshed options/futures context to update expiration-related intelligence.

In your recent fresh run it transitioned from:

```text
DEFERRED_INCOMPLETE_INPUT
```

during underlying-only finalization to:

```text
READY
AUTHORITY_REBUILT
```

after options became available.

That's exactly the expected coupling.

---

# 54. Continuous Learning

Finally:

```text
ContinuousLearningService
```

runs for:

```text
PAPER-PRIMARY
```

It updates:

```text
prediction capture
realized outcomes
probability calibration samples
execution-quality samples
```

So each options ingestion cycle also advances the performance-learning subsystem.

---

# 55. Reports written by a run

A normal options run writes several operational artifacts, including:

```text
reports/market_ingestion/options_manifest.json
reports/market_ingestion/options_latest.json

reports/market_ingestion/options_lifecycle_latest.json
reports/market_ingestion/options_finalization_latest.json

reports/market_ingestion/dealer_positioning_latest.json
```

plus the governed database tables.

The report hierarchy therefore lets us distinguish:

```text
raw ingestion
dealer refresh
shared finalization
M62 downstream advancement
```

rather than collapsing everything into a single success flag.

---

# 56. Locking / concurrency controls

There are several layers of lock protection.

At the scheduler level:

```text
m69_6_market_pipeline
```

prevents overlapping underlying/options hourly cycles.

At options-domain level:

```text
options_domain_ingestion.lock
```

protects the whole options domain.

Polygon snapshot persistence also has:

```text
options_ingestion.lock
```

And shared intelligence finalization has:

```text
shared_market_finalization.lock
```

This is deliberately redundant because different entry points can theoretically invoke pieces of the system.

---

# 57. What options ingestion does **not** do

There are also important boundaries.

It does **not** create the current Stock Intelligence opportunity population.

Underlying ingestion owns that.

It does **not** directly submit anything to IBKR.

Trade Builder / Execution Workspace and the governed execution pipeline own that.

It does **not** automatically run the M64 portfolio optimizer itself.

It produces/refreshes the opportunity-level decision authority that M64 portfolio intelligence subsequently evaluates.

And it does **not** make conditional reversal strategies executable merely because they exist.

---

# 58. My assessment of the current architecture

At this point I would characterize options ingestion as having **six distinct responsibilities**:

```text
1. Market-data acquisition
2. Market-data governance and historical lineage
3. Options-derived market intelligence
4. Opportunity strategy/contract construction
5. Option valuation and trade-plan construction
6. Decision-authority publication
```

That is powerful, but it also means `ingest_options_data.py` has become a very important production boundary.

It is no longer merely an ingestion script.

---

# 59. Things I believe are particularly strong today

The strongest parts are:

* Polygon is authoritative end-to-end for option quotes.
* canonical symbol/provider-symbol separation is explicit.
* raw daily compatibility storage is separated from immutable timestamped snapshots.
* volatility and liquidity lineage must succeed before downstream authority.
* dealer positioning refreshes from the same fresh snapshot.
* current Stock Intelligence authority is reused rather than recreated.
* `.15.6` guarantees fresh underlying before options.
* exact Stock run lineage is verified after options.
* strategy + contract selection is globally feasible, not sequentially naïve.
* option valuation uses current coherent exact market inputs.
* contradictory evidence can suppress execution without destroying useful opposite-direction candidates.
* READY lifecycle labels are reconciled against actual artifacts.
* partial/full advancement authority is fail-closed.
* governed no-trade outcomes are distinguished from real software failures.

Those are all institutional-grade design characteristics.

---

# 60. Areas I would still harden

I found several things worth improving, but I would **not change them blindly**.

### A. Provider filtering observability

We need explicit counts for:

```text
raw Polygon records
mapping failures
DTE-filtered
OI-filtered
volume-filtered
strike-distance-filtered
validation rejected
deduplicated
persisted
```

Right now some early drops are invisible.

### B. True insert vs update metrics

Postgres upsert accounting should distinguish:

```text
inserted
updated
unchanged
```

instead of reporting all successful upserts as inserts.

### C. Freshness at contract-selection level

We persist `quote_timestamp`, which is excellent.

I would verify that **contract optimization and valuation have explicit maximum quote-age gates**, not merely latest `quote_date`.

We've already seen how dangerous intraday freshness can be in execution.

### D. Snapshot completeness threshold

Today:

```text
some symbols missing → PARTIAL
```

but the pipeline can still proceed if there are positive volatility/liquidity rows.

We should decide whether institutional authority should require a hard minimum completeness threshold, perhaps:

```text
>= 99.x%
```

or use symbol-specific coverage requirements.

### E. Silent mapper failures

As mentioned, malformed Polygon rows should become visible diagnostic evidence.

### F. Futures API-key inconsistency

The futures stage keeps reporting missing Polygon/Massive key even though the option side clearly has Polygon credentials.

That is almost certainly environment/configuration plumbing rather than data availability.

### G. Option-data raw-history granularity

`option_contract_history` is same-day latest-state storage while immutable hourly history exists in `option_contract_snapshot`.

That's fine, but we should document this explicitly so nobody mistakenly uses `option_contract_history` for intraday historical research.

---

## The most important architectural conclusion

Your intuition earlier was exactly right:

**underlying and options are now tightly coupled.**

Today an options cycle depends directly on fresh:

```text
underlying price
trend
forecast
institutional participation
market context
Stock Intelligence
Inflection Intelligence
```

and then feeds back:

```text
volatility
liquidity
dealer positioning
options-enriched inflection
strategy selection
contract feasibility
mispricing
management
certification
decision authority
```

So I would now think of the production system not as two ingestion jobs, but as a single **market-decision refresh cycle**:

```text
UNDERLYING AUTHORITY
        +
OPTION AUTHORITY
        ↓
INSTITUTIONAL DECISION AUTHORITY
```

That is the architecture we effectively have today.

If you want, the next thing I would do is turn this source review into a **formal options-ingestion architecture/acceptance audit**: every stage, database table, lineage key, freshness contract, failure mode, and whether I rate it **PASS / HARDEN / DEFECT**. That would give us a concrete checklist for deciding whether options ingestion itself is production-complete.
