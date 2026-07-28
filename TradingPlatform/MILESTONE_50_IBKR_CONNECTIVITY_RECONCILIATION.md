# Milestone 50 — IBKR Paper Connectivity and Reconciliation

## Scope

This cumulative Milestone 50 package extends the IBKR paper-account foundation with read-only TWS/IB Gateway connectivity, managed-account verification, account-summary synchronization, broker-position snapshots, authoritative portfolio-position import, and reconciliation reporting.

## Safety invariants

- IBKR environment must be `PAPER`.
- The expected account must begin with `DU`.
- Every managed account exposed by the connected session must be a paper account.
- The registered account must be present in the connected session.
- The binding must remain `read_only=true`.
- Live trading and order submission remain disabled.
- No IBKR username, password, token, or credential is stored.

## Install the official IBKR Python API

Interactive Brokers distributes the Python API with its TWS API download. Install the Python client from the downloaded API package into the project virtual environment before attempting connectivity. Do not add account credentials to the project.

After installation, confirm:

```bash
uv run python -c "import ibapi; print('ibapi available')"
```

## TWS / IB Gateway configuration

1. Log in to the IBKR paper account in TWS or IB Gateway.
2. Enable socket API clients.
3. Use the registered paper port (`7497` for the current TWS binding).
4. Permit localhost (`127.0.0.1`).
5. Keep the platform binding in read-only mode for this phase.

## Validation

```bash
uv run python scripts/validate_m50_ibkr_connectivity_reconciliation.py
```

Expected after `ibapi` installation:

```text
READY_FOR_TWS_CONNECTION
```

## Connection test

With the paper TWS/IB Gateway session running:

```bash
uv run python scripts/test_ibkr_paper_connection.py \
  --account-id PAPER-PRIMARY
```

Expected:

```text
CONNECTED_READ_ONLY
```

## Synchronize and reconcile

```bash
uv run python scripts/sync_ibkr_paper_account.py \
  --account-id PAPER-PRIMARY
```

This operation:

- Verifies the connected paper account.
- Imports an account summary snapshot.
- Imports broker position snapshots.
- Reconciles positions into `portfolio_positions`.
- Persists a `broker_reconciliation_runs` record.
- Keeps order submission disabled.

To report differences without importing positions:

```bash
uv run python scripts/sync_ibkr_paper_account.py \
  --account-id PAPER-PRIMARY \
  --no-import-positions
```

## Tests

```bash
uv run pytest -q \
  tests/milestone50/test_m50_ibkr_paper_foundation.py \
  tests/milestone50/test_m50_ibkr_connectivity_reconciliation.py
```

Expected: `6 passed`.
