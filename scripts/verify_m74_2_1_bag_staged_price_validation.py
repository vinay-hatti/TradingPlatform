from pathlib import Path
s=Path('src/trading_ai/broker/ibkr/order_transport.py').read_text()
submit=s[s.index('def submit_combo_order'):s.index('def prepare_existing_order_for_modify')]
for item in ['callback=="ERROR" and code==110','IBKR_TRANSMITTED_BAG_PRICE_GRID_DISCOVERY','candidate_attempts']:
    assert item in submit, item
assert 'validate_combo_limit_price' not in submit
print('M74.2.1 superseded by M74.5 broker-authoritative BAG price-grid discovery: PASSED')
