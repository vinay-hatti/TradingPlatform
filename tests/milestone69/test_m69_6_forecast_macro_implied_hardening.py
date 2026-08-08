import importlib.util
from pathlib import Path

def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

def test_recursive_forecast_field_resolution():
    m=load('forecast_resolver',Path('src/trading_ai/option_valuation_intelligence/events/forecast_resolver.py'))
    assert m._find_numeric({'forecast':{'expected_return_pct':-4.2}})==(4.2,'forecast.expected_return_pct')

def test_atm_pair_uses_shared_nearest_strike():
    m=load('implied_move',Path('src/trading_ai/option_valuation_intelligence/events/implied_move.py'))
    rows=[{'option_type':'call','strike':100},{'option_type':'put','strike':100},{'option_type':'call','strike':105},{'option_type':'put','strike':105}]
    c,p,k=m._atm_pair(rows,102)
    assert k==100 and c['strike']==p['strike']==100

def test_raw_horizon_iv_floor_removed():
    src=Path('src/trading_ai/option_valuation_intelligence/events/implied_move.py').read_text()
    assert 'max(straddle,variance)' not in src
    assert 'TERM_VARIANCE_ISOLATION' in src
