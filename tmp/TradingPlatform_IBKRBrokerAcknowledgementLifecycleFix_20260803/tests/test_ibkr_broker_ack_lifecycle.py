from pathlib import Path
import sys
root=Path(sys.argv[1] if len(sys.argv)>1 else '.').resolve()
t=(root/'src/trading_ai/broker/ibkr/order_transport.py').read_text()
s=(root/'src/trading_ai/broker/ibkr/order_service.py').read_text()
assert 'await_order_acknowledgement' in t
assert 'begin_order_submission' in t
assert 'AWAITING_BROKER_ACK' in t
assert 'broker_acknowledgement' in s
assert 'last_error=str(acknowledgement.get("error")' in s
assert 'status="SUBMITTED",filled_quantity=0.0' not in s
print('IBKR broker acknowledgement lifecycle contract assertions passed.')
