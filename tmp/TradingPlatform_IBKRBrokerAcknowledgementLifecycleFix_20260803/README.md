# IBKR Broker Acknowledgement Lifecycle Fix

This patch stops treating a locally allocated IBKR order ID as proof of broker submission.

## New submission states

- `AWAITING_BROKER_ACK`: `placeOrder()` returned, but no `openOrder`, `orderStatus`, or order-specific `error` callback arrived before timeout.
- Broker callback status such as `PRESUBMITTED` or `SUBMITTED`: IBKR acknowledged the order.
- `REJECTED`: IBKR returned an order-specific error callback.

The transport logs `placeOrder` send/return and all non-informational IBKR errors. Callback evidence is persisted in `broker_orders.raw_json.broker_acknowledgement`; rejection text is persisted in `last_error`.

## Important

Existing rows 5, 6, and 7 were created before this fix and cannot be retroactively proven acknowledged. After applying, cancel or reconcile those stale rows and submit one new controlled paper order to validate callback receipt.
