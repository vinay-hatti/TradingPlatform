from trading_ai.futures_intelligence.service import PRODUCT_INDEX, clamp

def test_index_mapping_is_binding():
    assert PRODUCT_INDEX == {'ES':'SPX','NQ':'NDX','RTY':'RUT'}

def test_confirmation_clamp():
    assert clamp(110)==100
    assert clamp(-10)==0
