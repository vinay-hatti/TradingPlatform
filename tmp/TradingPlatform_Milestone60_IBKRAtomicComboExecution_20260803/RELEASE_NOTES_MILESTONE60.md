# Release Notes — Milestone 60

## Added
- Native IBKR BAG option-combo contracts.
- Contract-ID resolution with deterministic matching.
- Atomic multi-leg limit-order submission.
- Ratio normalization using greatest common divisor.
- Signed net debit/credit limit-price calculation.
- Combo provenance in canonical and broker-order metadata.
- OMS atomic-combo badge and action wording.

## Preserved
- Milestone 50 paper-account governance.
- Milestone 59 explicit confirmation and execution lifecycle.
- Existing single-leg option submission.
- Broker synchronization, cancellation, audit, and portfolio handoff.

## Database
No migration required; existing JSON metadata and order fields store combo details.
