from trading_ai.option_valuation_intelligence.engine import InstitutionalOptionValuationEngine

def test_underpriced_contract_has_explainable_edge():
 r=InstitutionalOptionValuationEngine().evaluate(opportunity={'direction':'BULLISH','dealer_score':72,'relative_strength':75},contract={'bid':2.8,'ask':3.0,'underlying_price':100,'strike':105,'dte':45,'right':'C','implied_volatility':0.20,'realized_volatility_20d':0.34,'liquidity_score':90},inflection={'inflection_score':78,'direction':'BULLISH'},siblings=[{'mid':3.5},{'mid':3.3}])
 assert r['fair_value']>0 and r['market_mid']>0
 assert r['classification'] in {'STRONG_UNDERPRICED','MODERATELY_UNDERPRICED','FAIR_VALUE','MODERATELY_OVERPRICED','STRONG_OVERPRICED'}
 assert isinstance(r['mispricing_pct'], float)
 assert len(r['components'])>=8 and r['evidence'] and r['invalidation']
 assert 0<=r['confidence']<=100 and 0<=r['stability_index']<=100

def test_wide_spread_reduces_execution_quality():
 e=InstitutionalOptionValuationEngine()
 tight=e.evaluate(opportunity={'direction':'BULLISH'},contract={'bid':4.9,'ask':5.1,'mid':5,'underlying_price':100,'strike':100,'dte':30,'right':'C','implied_volatility':.25,'realized_volatility_20d':.25},inflection={})
 wide=e.evaluate(opportunity={'direction':'BULLISH'},contract={'bid':3,'ask':7,'mid':5,'underlying_price':100,'strike':100,'dte':30,'right':'C','implied_volatility':.25,'realized_volatility_20d':.25},inflection={})
 assert tight['liquidity']['score']>wide['liquidity']['score']
 assert wide['conflicting_evidence']

def test_state_hash_is_deterministic():
 e=InstitutionalOptionValuationEngine(); kw=dict(opportunity={'direction':'BEARISH'},contract={'mid':2,'underlying_price':50,'strike':45,'dte':20,'right':'P','implied_volatility':.4,'realized_volatility_20d':.35},inflection={'inflection_score':65,'direction':'BEARISH'})
 assert e.evaluate(**kw)['state_hash']==e.evaluate(**kw)['state_hash']
