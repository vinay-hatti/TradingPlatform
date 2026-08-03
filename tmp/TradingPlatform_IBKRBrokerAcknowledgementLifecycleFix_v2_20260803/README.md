# IBKR Broker Acknowledgement Lifecycle Fix v2

Version-specific full-file replacement for the current Milestone 60 IBKR transport and service. This replaces the failed marker-based patcher.

It preserves atomic BAG support and changes order persistence so local `placeOrder()` dispatch is not treated as broker acknowledgement. New orders become `PRESUBMITTED`/`SUBMITTED`/`FILLED` only after `openOrder` or `orderStatus`; order-specific errors become `REJECTED`; callback timeouts become `AWAITING_BROKER_ACK`.

No migration is required. Existing pre-fix rows are not rewritten.
