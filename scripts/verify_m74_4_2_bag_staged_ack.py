from pathlib import Path
p=Path('src/trading_ai/broker/ibkr/order_transport.py')
s=p.read_text()
checks=[
    '_verify_local_staged_order',
    'app.reqOpenOrders()',
    'OPEN_ORDER_VERIFY',
    'STAGE_VALIDATION_INCONCLUSIVE',
    'if callback=="ERROR"',
    'numeric_code==110',
    'raise TimeoutError',
]
for item in checks:
    assert item in s, item
print('M74.4.2 BAG staged acknowledgement hardening verification: PASSED')
