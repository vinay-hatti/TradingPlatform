# Milestone 60 — Native IBKR Atomic Combo Execution

This cumulative enhancement extends the Milestone 59 OMS with native IBKR `BAG` combo-contract submission for governed multi-leg option plans.

## Scope

- Resolves option-leg `conId` values through IBKR contract-details requests.
- Constructs one `BAG` contract with 2–4 combo legs.
- Preserves each governed leg ratio and BUY/SELL action.
- Submits one atomic net-price paper `LMT` order.
- Supports signed net prices: positive debit and negative credit.
- Persists `security_type=BAG`, resolved legs, atomic-combo provenance, and broker order lineage.
- Reuses existing broker synchronization, cancellation, audit, and Portfolio Intelligence handoff.
- Retains the existing single-leg order path.

## Safety and governance

- Paper accounts only (`DU...`).
- Live trading remains disabled.
- Existing routing activation remains authoritative.
- Exact confirmation remains required: `SUBMIT PAPER INTENT <intent-id>`.
- No autonomous submission.
- Submission fails before order placement if any option contract cannot be resolved.

## Apply

```bash
./APPLY_MILESTONE60_IBKR_ATOMIC_COMBO.sh /Users/vinay.hatti/TradingPlatform
```

No database migration is required.

## Validate

```bash
./VALIDATE_MILESTONE60_IBKR_ATOMIC_COMBO.sh /Users/vinay.hatti/TradingPlatform
```

## Controlled paper validation

1. Keep TWS or IB Gateway connected to the registered paper account.
2. Open `#/execution-workspace`.
3. Select the approved multi-leg intent.
4. Confirm the displayed `IBKR BAG · ATOMIC` badge and net limit price.
5. Submit using the exact confirmation phrase shown by the UI.
6. Verify `broker_orders.security_type = 'BAG'` and `raw_json.atomic_combo = true`.
7. Synchronize broker status from the OMS.
8. Cancel the controlled paper order if it is not intended to fill.

The system never submits the legs independently.
