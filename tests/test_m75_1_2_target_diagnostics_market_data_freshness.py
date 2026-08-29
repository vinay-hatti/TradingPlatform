from pathlib import Path
import ast
ROOT=Path(__file__).resolve().parents[1]

def _helper():
    src=(ROOT/'src/trading_ai/execution_intelligence/service.py').read_text()
    tree=ast.parse(src)
    node=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='_directional_target_revalidation')
    ns={};exec(compile(ast.Module(body=[node],type_ignores=[]),'<helper>','exec'),ns)
    return ns['_directional_target_revalidation']

class Dummy:
    def __init__(self,direction,targets,strategy='CALL_DIAGONAL'):
        self.strategy=strategy
        self.metadata_json={'underlying_thesis':{'direction':direction},'dynamic_management':{'underlying_targets':targets}}

def test_bullish_skipped_target_diagnostics_include_distance_and_original_number():
    out=_helper()(Dummy('BULLISH',[7472.1326,7562.61,7781.2586]),7748.50)
    assert out['effective_targets']==[7781.2586]
    d=out['skipped_target_details']
    assert [x['original_target_number'] for x in d]==[1,2]
    assert d[0]['label']=='Target 1'
    assert d[0]['target_value']==7472.1326
    assert d[0]['current_underlying']==7748.50
    assert d[0]['distance_label']=='EXCEEDED_BY'
    assert abs(d[0]['distance']-276.3674)<1e-6
    assert abs(d[1]['distance']-185.89)<1e-6

def test_bearish_skipped_target_diagnostics_use_undercut_semantics():
    out=_helper()(Dummy('BEARISH',[104,96,92],strategy='BEAR_PUT_SPREAD'),95)
    assert out['effective_targets']==[92]
    d=out['skipped_target_details']
    assert [x['target_value'] for x in d]==[104,96]
    assert all(x['distance_label']=='UNDERCUT_BY' for x in d)
    assert d[0]['distance']==9
    assert d[1]['distance']==1

def test_execution_evidence_separates_underlying_and_option_market_data_age():
    src=(ROOT/'src/trading_ai/execution_intelligence/service.py').read_text()
    assert "'underlying_quote_age_seconds':round(underlying_quote_age_seconds,6)" in src
    assert "'option_quote_age_seconds':round(max_age,6)" in src
    assert "underlying_quote_timestamp=(latest.get('underlying_quote') or {}).get('quote_timestamp')" in src

def test_ui_renders_requested_skipped_target_evidence_and_separate_freshness():
    src=(ROOT/'ui/workstation/src/ExecutionWorkspacePage.tsx').read_text()
    for marker in ('Skipped targets','Current underlying','Exceeded by','Undercut by','Underlying quote age','Option quote age'):
        assert marker in src
    assert 'skipped_target_details' in src
