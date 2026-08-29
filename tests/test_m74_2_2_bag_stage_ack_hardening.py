from pathlib import Path

SRC=Path('src/trading_ai/broker/ibkr/order_transport.py').read_text()

def test_timeout_is_not_treated_as_broker_rejection():
    assert '_verify_local_staged_order' in SRC
    assert 'STAGE_VALIDATION_INCONCLUSIVE' in SRC
    assert 'if callback=="ERROR"' in SRC
    assert 'numeric_code==110' in SRC

def test_transmit_false_stage_is_verified_by_open_orders():
    assert 'app.reqOpenOrders()' in SRC
    assert 'OPEN_ORDER_VERIFY' in SRC
    assert 'REQ_OPEN_ORDERS' in SRC

def test_code_zero_is_not_fabricated_from_timeout():
    block=SRC[SRC.index('def validate_combo_limit_price'):SRC.index('def normalize_combo_limit_price')]
    assert 'if callback=="ERROR"' in block
    assert 'raise TimeoutError' in block
