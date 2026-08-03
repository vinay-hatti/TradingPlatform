# IBKR Order Attribute Compatibility Fix

For installed `ibapi 9.81.1-1`, `Order()` defaults `eTradeOnly=True` and `firmQuoteOnly=True`. Modern TWS/Gateway rejects these fields with errors 10268/10269. This package explicitly sets both to `False` for single-leg and BAG combo orders. `nbboPriceCap` remains unchanged at IBKR's unset sentinel.

No database migration is required.
