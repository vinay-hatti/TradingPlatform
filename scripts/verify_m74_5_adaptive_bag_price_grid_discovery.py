from pathlib import Path
s=Path('src/trading_ai/broker/ibkr/order_transport.py').read_text()
submit=s[s.index('def submit_combo_order'):s.index('def prepare_existing_order_for_modify')]
modify=s[s.index('def modify_combo_order'):s.index('def wait_for_order_acknowledgement')]
checks=[
    'IBKR_TRANSMITTED_BAG_PRICE_GRID_DISCOVERY',
    'callback=="ERROR" and code==110',
    'IBKR_ACK_INCONCLUSIVE',
    'IBKR_PRICE_GRID_EXHAUSTED',
    'candidate_attempt_count',
]
for item in checks:
    assert item in submit, item
assert 'validate_combo_limit_price' not in submit
assert 'validate_combo_limit_price' not in modify
assert 'transmit=False' not in submit
print('M74.5 adaptive BAG price-grid discovery verification: PASSED')
