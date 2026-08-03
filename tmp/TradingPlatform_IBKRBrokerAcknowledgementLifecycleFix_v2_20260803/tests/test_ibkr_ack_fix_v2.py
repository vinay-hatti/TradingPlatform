from pathlib import Path
import sys
root=Path(sys.argv[1]) if len(sys.argv)>1 else Path.cwd()
t=(root/'src/trading_ai/broker/ibkr/order_transport.py').read_text()
s=(root/'src/trading_ai/broker/ibkr/order_service.py').read_text()
assert 'wait_for_order_acknowledgement' in t
assert 'begin_order_ack' in t
assert 'OPEN_ORDER' in t and 'ORDER_STATUS' in t and 'AWAITING_BROKER_ACK' in t
assert 'broker_acknowledgement' in s
assert 'status=str(acknowledgement.get("status")' in s
assert 'submit_combo_order' in t and 'atomic_combo' in s
print('IBKR broker acknowledgement lifecycle fix v2 assertions passed.')
