# Milestone 50 — IBKR Paper Order Routing

Adds explicitly activated, paper-only IBKR order routing. Connectivity does not enable submission. Operators must run the exact confirmation command after migration and validation. Broker order IDs, permanent IDs, statuses, and executions are persisted in PostgreSQL. Live accounts are rejected and `live_trading_enabled` remains false.

## Activation

```bash
uv run python scripts/manage_ibkr_paper_order_routing.py activate \
  --account-id PAPER-PRIMARY \
  --confirmation "ENABLE IBKR PAPER ORDERS PAPER-PRIMARY"
```

Disable immediately with:

```bash
uv run python scripts/manage_ibkr_paper_order_routing.py disable \
  --account-id PAPER-PRIMARY --reason "operator pause"
```

Do not activate until TWS paper connectivity and account reconciliation are healthy.
