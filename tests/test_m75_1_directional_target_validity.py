from pathlib import Path
import ast

ROOT=Path(__file__).resolve().parents[1]

def test_generation_filters_against_current_underlying():
    src=(ROOT/'src/trading_ai/stock_intelligence/position_intelligence.py').read_text()
    assert "current=_last_close(profile)" in src
    assert "def _valid(price:float|None, current_underlying:float, bull:bool)" in src
    assert "self._valid(price,current,bull)" in src
    assert "CROSSED_CURRENT_UNDERLYING_OR_INVALID_PRICE" in src


def test_option_integration_hard_generation_gate():
    src=(ROOT/'src/trading_ai/stock_intelligence/option_integration.py').read_text()
    assert "NO_DIRECTIONALLY_VALID_UNDERLYING_TARGETS" in src
    assert "CROSSED_UNDERLYING_TARGETS_SKIPPED" in src
    assert "targets = sorted(set(targets), reverse=not bullish)" in src


def _load_revalidation_helper():
    src=(ROOT/'src/trading_ai/execution_intelligence/service.py').read_text()
    tree=ast.parse(src)
    node=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='_directional_target_revalidation')
    module=ast.Module(body=[node],type_ignores=[])
    ns={}
    exec(compile(module,'<helper>','exec'),ns)
    return ns['_directional_target_revalidation']

class Dummy:
    def __init__(self,strategy,direction,targets):
        self.strategy=strategy
        self.metadata_json={'underlying_thesis':{'direction':direction},'dynamic_management':{'underlying_targets':targets}}

def test_live_preflight_skips_crossed_bullish_targets():
    fn=_load_revalidation_helper()
    out=fn(Dummy('BULL_CALL_SPREAD','BULLISH',[7562.61,7781.26,8000]),7748)
    assert out['skipped_targets']==[7562.61]
    assert out['effective_targets']==[7781.26,8000.0]
    assert out['valid_target_available'] is True
    assert out['status']=='FILTERED'


def test_live_preflight_skips_crossed_bearish_targets():
    fn=_load_revalidation_helper()
    out=fn(Dummy('BEAR_PUT_SPREAD','BEARISH',[104,96,92,87]),100)
    assert out['skipped_targets']==[104.0]
    assert out['effective_targets']==[96.0,92.0,87.0]
    assert out['valid_target_available'] is True


def test_live_preflight_blocks_if_no_valid_directional_target():
    fn=_load_revalidation_helper()
    out=fn(Dummy('LONG_CALL','BULLISH',[90,95,100]),101)
    assert out['effective_targets']==[]
    assert out['valid_target_available'] is False
    assert out['status']=='NO_VALID_TARGETS'


def test_fill_activation_uses_preflight_effective_targets():
    src=(ROOT/'src/trading_ai/execution_workspace/service.py').read_text()
    assert "target_revalidation=dict(gate_evidence.get('target_revalidation') or {})" in src
    assert "targets=list(target_revalidation.get('effective_targets') or management.get('underlying_targets') or [])" in src


def test_ui_displays_target_revalidation():
    src=(ROOT/'ui/workstation/src/ExecutionWorkspacePage.tsx').read_text()
    assert 'Directional target revalidation' in src
    assert 'Skipped crossed targets' in src
    assert 'Effective targets' in src
