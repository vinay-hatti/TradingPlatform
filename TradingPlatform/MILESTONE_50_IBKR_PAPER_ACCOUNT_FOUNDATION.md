# Milestone 50 — IBKR Paper Account Foundation

This cumulative package adds a guarded Interactive Brokers paper-account binding and synchronization foundation.

## Safety policy

- Only accounts beginning with `DU` are accepted.
- The broker environment is fixed to `PAPER`.
- `live_trading_enabled` is always false.
- Registration stores no password, token, or TWS credentials.
- Initial registration is read-only.
- Polygon remains authoritative for scanner and options analytics market data.

## When to add your actual IBKR paper account

Add the account identifier only after:

1. `uv run alembic upgrade head` succeeds.
2. `uv run pytest -q tests/milestone50/test_m50_ibkr_paper_foundation.py` passes.
3. `uv run python scripts/validate_m50_ibkr_paper_foundation.py` reports `READY_FOR_ACCOUNT_REGISTRATION`.

Then register it with:

```bash
uv run python scripts/register_ibkr_paper_account.py \
  --internal-account-id PAPER-PRIMARY \
  --broker-account-id DUXXXXXXX \
  --base-currency USD \
  --host 127.0.0.1 \
  --port 7497 \
  --client-id 50
```

Do not provide passwords or authentication secrets. TWS/IB Gateway authentication remains local.

The real IBKR socket sync remains disabled in this foundation package until the subsequent execution/connectivity phase adds and certifies the official client transport.
