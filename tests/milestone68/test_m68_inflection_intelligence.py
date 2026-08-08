from trading_ai.inflection_intelligence.engine import Bar, InstitutionalInflectionEngine

def bars(up=True):
    out=[]
    for i in range(40):
        c=100+i*.5 if up else 120-i*.5
        out.append(Bar(c,c+1,c-1,1000+i*25))
    return out

def test_engine_is_explainable_and_bounded():
    r=InstitutionalInflectionEngine().evaluate('TEST',bars(),candidate_payload={'implied_volatility':.18},dealer_payload={'gamma_score':75,'wall_migration_score':80,'hedge_pressure_score':70},breadth_score=72)
    assert 0<=r['inflection_score']<=100
    assert 0<=r['confidence']<=100
    assert set(r['components'])=={'trend','structure','dealer','volatility','participation','breadth','liquidity'}
    assert r['evidence'] and r['state_hash']

def test_bullish_and_bearish_direction():
    e=InstitutionalInflectionEngine()
    assert e.evaluate('UP',bars(True),dealer_payload={'gamma_score':70})['direction']=='BULLISH'
    assert e.evaluate('DOWN',bars(False),dealer_payload={'gamma_score':30})['direction']=='BEARISH'

def test_requires_history():
    try: InstitutionalInflectionEngine().evaluate('X',bars()[:10])
    except ValueError: pass
    else: raise AssertionError('expected ValueError')
