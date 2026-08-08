from trading_ai.option_valuation_intelligence.engine import InstitutionalOptionValuationEngine


def base_contract(**overrides):
    data={'bid':2.8,'ask':3.0,'underlying_price':100,'strike':105,'dte':45,'right':'C','implied_volatility':0.20,'realized_volatility_20d':0.34,'liquidity_score':90}
    data.update(overrides); return data


def test_fair_value_is_independent_of_market_mid_blending():
    e=InstitutionalOptionValuationEngine()
    a=e.evaluate(opportunity={'direction':'BULLISH','dealer_score':72},contract=base_contract(mid=2.9),inflection={'inflection_score':78,'direction':'BULLISH'},siblings=[{'implied_volatility':.27},{'implied_volatility':.29}])
    b=e.evaluate(opportunity={'direction':'BULLISH','dealer_score':72},contract=base_contract(mid=4.5,bid=4.4,ask=4.6),inflection={'inflection_score':78,'direction':'BULLISH'},siblings=[{'implied_volatility':.27},{'implied_volatility':.29}])
    assert abs(a['model_fair_value']-b['model_fair_value']) < 1e-9
    assert a['mispricing_pct'] != b['mispricing_pct']


def test_five_band_classification_is_discriminating():
    e=InstitutionalOptionValuationEngine()
    under=e.evaluate(opportunity={'direction':'BULLISH','dealer_score':75},contract=base_contract(mid=1.5,bid=1.45,ask=1.55),inflection={'inflection_score':85,'direction':'BULLISH'},siblings=[{'implied_volatility':.35},{'implied_volatility':.36}])
    over=e.evaluate(opportunity={'direction':'BULLISH','dealer_score':40},contract=base_contract(mid=8,bid=7.9,ask=8.1,realized_volatility_20d=.12),inflection={'inflection_score':35,'direction':'BEARISH'},siblings=[{'implied_volatility':.18},{'implied_volatility':.19}])
    assert 'UNDERPRICED' in under['classification']
    assert 'OVERPRICED' in over['classification']


def test_all_five_mispricing_domains_report_coverage():
    e=InstitutionalOptionValuationEngine()
    r=e.evaluate(
        opportunity={'direction':'BULLISH','dealer_score':70,'event_pricing_score':65,'peer_implied_volatility':.28},
        contract=base_contract(forecast_volatility=.32),
        inflection={'inflection_score':75,'direction':'BULLISH'},
        siblings=[{'implied_volatility':.26},{'implied_volatility':.27}],
    )
    coverage=r['component_coverage']
    for domain in ('volatility','surface','relative_value','event','dealer_flow','liquidity'):
        assert domain in coverage and coverage[domain]['available']
    assert r['component_coverage_pct'] >= 75


def test_missing_inputs_are_explicit_not_silently_exact():
    r=InstitutionalOptionValuationEngine().evaluate(opportunity={'direction':'BULLISH'},contract={'mid':2,'underlying_price':50,'strike':50,'dte':30,'right':'C'},inflection={})
    assert r['component_coverage']['surface']['quality']=='NEUTRAL_FALLBACK'
    assert r['component_coverage']['event']['available'] is False
    assert any('Neutral fallbacks used' in x for x in r['conflicting_evidence'])

def test_serialized_contract_recommendation_uses_legs_and_underlying_context():
    e=InstitutionalOptionValuationEngine()
    contract={
      'strategy':'LONG_CALL', 'liquidity_score':90,
      'legs':[{'side':'BUY','option_type':'C','strike':100,'bid':4.8,'ask':5.2,'last':5.0,'implied_volatility':0.30,'quantity_ratio':1}],
    }
    r=e.evaluate(opportunity={'direction':'BULLISH','underlying_price':103,'dealer_score':65},contract=contract,inflection={'inflection_score':72,'direction':'BULLISH'})
    assert r['market_mid'] == 5.0
    assert r['model_fair_value'] != r['market_mid']
    assert r['mispricing_pct'] != 0.0
    assert r['component_coverage']['liquidity']['available'] is True
    assert r['component_coverage']['dealer_flow']['available'] is True


def test_vertical_spread_is_valued_as_signed_multi_leg_structure():
    e=InstitutionalOptionValuationEngine()
    contract={'strategy':'BULL_CALL_SPREAD','legs':[
      {'side':'BUY','option_type':'C','strike':100,'bid':5.8,'ask':6.2,'implied_volatility':0.30,'quantity_ratio':1},
      {'side':'SELL','option_type':'C','strike':110,'bid':2.3,'ask':2.6,'implied_volatility':0.28,'quantity_ratio':1},
    ]}
    r=e.evaluate(opportunity={'direction':'BULLISH','underlying_price':104,'dealer_score':55},contract=contract,inflection={'inflection_score':65,'direction':'BULLISH'})
    assert 3.0 < r['market_mid'] < 4.0
    assert abs(r['model_fair_value']-r['market_mid']) > 0.001
    assert r['component_coverage']['liquidity']['available'] is True
