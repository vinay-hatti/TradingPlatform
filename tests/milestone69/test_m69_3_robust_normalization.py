from trading_ai.option_valuation_intelligence.engine import InstitutionalOptionValuationEngine


def test_near_zero_vertical_uses_robust_reference_and_bounded_edge():
    result = InstitutionalOptionValuationEngine().evaluate(
        opportunity={'direction': 'BULLISH', 'underlying_price': 100, 'dealer_score': 60},
        contract={'strategy': 'BULL_CALL_SPREAD', 'liquidity_score': 90, 'legs': [
            {'side': 'BUY', 'option_type': 'C', 'strike': 100, 'bid': 5.0, 'ask': 5.2, 'implied_volatility': .30},
            {'side': 'SELL', 'option_type': 'C', 'strike': 105, 'bid': 5.0, 'ask': 5.2, 'implied_volatility': .29},
        ]},
        inflection={'inflection_score': 70, 'direction': 'BULLISH'},
    )
    assert result['low_net_premium'] is True
    assert result['reference_value'] >= .25
    assert -100 <= result['mispricing_pct'] <= 100


def test_execution_penalty_is_capped_and_not_full_half_spread():
    result = InstitutionalOptionValuationEngine().evaluate(
        opportunity={'direction': 'BULLISH', 'underlying_price': 100, 'dealer_score': 60},
        contract={'strategy': 'LONG_CALL', 'liquidity_score': 75, 'legs': [
            {'side': 'BUY', 'option_type': 'C', 'strike': 100, 'bid': 4.0, 'ask': 6.0, 'implied_volatility': .30},
        ]},
        inflection={'inflection_score': 70, 'direction': 'BULLISH'},
    )
    assert abs(result['components']['execution_edge_pct']) <= 8.01
    assert result['liquidity']['expected_slippage'] < 1.0


def test_leg_iv_and_sibling_surface_are_detected_from_serialized_legs():
    result = InstitutionalOptionValuationEngine().evaluate(
        opportunity={'direction': 'BULLISH', 'underlying_price': 100, 'dealer_score': 60},
        contract={'strategy': 'LONG_CALL', 'liquidity_score': 90, 'legs': [
            {'side': 'BUY', 'option_type': 'C', 'strike': 100, 'bid': 4.9, 'ask': 5.1, 'implied_volatility': .30},
        ]},
        inflection={'inflection_score': 70, 'direction': 'BULLISH'},
        siblings=[
            {'legs': [{'side': 'BUY', 'option_type': 'C', 'strike': 105, 'bid': 3, 'ask': 3.2, 'implied_volatility': .32}]},
            {'legs': [{'side': 'BUY', 'option_type': 'C', 'strike': 110, 'bid': 2, 'ask': 2.2, 'implied_volatility': .34}]},
        ],
    )
    assert result['component_coverage']['volatility']['available'] is True
    assert result['component_coverage']['surface']['available'] is True
    assert result['surface']['neighbor_count'] == 2


def test_credit_package_preserves_signed_price_but_uses_positive_reference():
    result = InstitutionalOptionValuationEngine().evaluate(
        opportunity={'direction': 'BULLISH', 'underlying_price': 100, 'dealer_score': 55},
        contract={'strategy': 'BULL_PUT_SPREAD', 'liquidity_score': 90, 'legs': [
            {'side': 'SELL', 'option_type': 'P', 'strike': 100, 'bid': 4.8, 'ask': 5.0, 'implied_volatility': .31},
            {'side': 'BUY', 'option_type': 'P', 'strike': 95, 'bid': 2.8, 'ask': 3.0, 'implied_volatility': .30},
        ]},
        inflection={'inflection_score': 65, 'direction': 'BULLISH'},
    )
    assert result['market_mid'] < 0
    assert result['reference_value'] > 0
    assert -100 <= result['mispricing_pct'] <= 100
