from pathlib import Path
SRC=Path('src/trading_ai/broker/ibkr/order_transport.py').read_text()

def test_combo_candidate_prices_are_grid_based_and_economically_bounded():
    assert 'normalize_signed_combo_price' in SRC
    assert 'TRADING_AI_IBKR_COMBO_PRICE_INCREMENT_CANDIDATES' in SRC
    assert 'BAG_PRICE_GRID_DISCOVERY' in SRC

def test_combo_submission_does_not_request_bag_contract_details_or_require_staging():
    block=SRC[SRC.index('def submit_combo_order'):SRC.index('def prepare_existing_order_for_modify')]
    assert '_request_contract_rule_details' not in block
    assert 'validate_combo_limit_price' not in block
    assert 'callback=="ERROR" and code==110' in block

def test_combo_submission_uses_broker_authoritative_error_110_discovery():
    block=SRC[SRC.index('def submit_combo_order'):SRC.index('def prepare_existing_order_for_modify')]
    assert 'app.placeOrder' in block
    assert 'IBKR_PRICE_GRID_EXHAUSTED' in block
    assert 'candidate_attempts' in block
