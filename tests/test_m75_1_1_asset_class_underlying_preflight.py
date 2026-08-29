from pathlib import Path
import ast

ROOT=Path(__file__).resolve().parents[1]

def _load_revalidation_helper():
    src=(ROOT/'src/trading_ai/execution_intelligence/service.py').read_text()
    tree=ast.parse(src)
    node=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='_directional_target_revalidation')
    ns={};exec(compile(ast.Module(body=[node],type_ignores=[]),'<helper>','exec'),ns)
    return ns['_directional_target_revalidation']

class Dummy:
    def __init__(self,strategy='CALL_DIAGONAL',direction='BULLISH',targets=None):
        self.strategy=strategy
        self.metadata_json={'underlying_thesis':{'direction':direction},'dynamic_management':{'underlying_targets':targets or [7472.1326,7562.61,7781.2586]}}

def test_directional_revalidation_fails_closed_when_underlying_missing():
    out=_load_revalidation_helper()(Dummy(),None)
    assert out['underlying_price'] is None
    assert out['underlying_price_available'] is False
    assert out['effective_targets']==[]
    assert out['valid_target_available'] is False
    assert out['status']=='UNDERLYING_UNAVAILABLE'

def test_directional_revalidation_does_not_coerce_missing_underlying_to_zero():
    out=_load_revalidation_helper()(Dummy(),0)
    assert out['underlying_price'] is None
    assert out['underlying_price_available'] is False
    assert out['status']=='UNDERLYING_UNAVAILABLE'

def test_spx_live_preflight_routes_index_underlying_to_index_quote():
    src=(ROOT/'src/trading_ai/execution_intelligence/service.py').read_text()
    assert "ticker.startswith('I:')" in src
    assert "u=provider.index_quote(polygon_underlying_ticker)" in src
    assert "underlying_source='POLYGON_INDEX_SNAPSHOT'" in src
    assert "u=provider.underlying_quote(m.symbol)" in src
    assert "underlying_source='POLYGON_STOCK_SNAPSHOT'" in src

def test_execution_checks_include_underlying_availability_and_block():
    src=(ROOT/'src/trading_ai/execution_intelligence/service.py').read_text()
    assert "'underlying_price_available':bool(target_revalidation['underlying_price_available'])" in src
    assert "elif not checks['underlying_price_available']:decision='BLOCK'" in src
    assert "'polygon_underlying_ticker':latest.get('polygon_underlying_ticker')" in src

def test_polygon_provider_index_quote_accepts_prefixed_ticker():
    from trading_ai.execution_intelligence.provider import PolygonDirectExecutionQuoteProvider
    p=object.__new__(PolygonDirectExecutionQuoteProvider)
    calls=[]
    def fake_get(path,params=None):
        calls.append((path,params));return {'results':[{'ticker':'I:SPX','value':7748.25,'last_updated':1786568400000000000}]}
    p._get=fake_get
    q=p.index_quote('I:SPX')
    assert q.instrument=='I:SPX'
    assert q.instrument_type=='INDEX'
    assert q.last==7748.25
    assert calls[0][0]=='/v3/snapshot/indices'
    assert calls[0][1]['ticker']=='I:SPX'

def test_ui_shows_unavailable_and_underlying_source():
    src=(ROOT/'ui/workstation/src/ExecutionWorkspacePage.tsx').read_text()
    assert "underlying_price_available?money(tr.underlying_price):'UNAVAILABLE'" in src
    assert 'Underlying source:' in src
    assert 'directional target validation fails closed' in src
