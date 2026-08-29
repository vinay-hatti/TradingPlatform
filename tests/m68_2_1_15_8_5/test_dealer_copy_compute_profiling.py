from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]

def test_copy_path_and_fallbacks_present():
    s=(ROOT/'src/trading_ai/institutional_market_structure/service.py').read_text()
    assert 'POSTGRES_COPY_SINGLE_WRITER' in s
    assert 'copy_expert' in s
    assert 'SQLALCHEMY_BULK_FALLBACK' in s
    assert 'SYMBOL_FALLBACK_AFTER_COPY_AND_BULK_FAILURE' in s

def test_compute_domain_profiling_present():
    r=(ROOT/'src/trading_ai/institutional_market_structure/refresh.py').read_text()
    e=(ROOT/'src/trading_ai/institutional_market_structure/engine.py').read_text()
    assert 'compute_domain_profiles' in r
    assert 'metrics_normalization_seconds' in e
    assert 'strike_aggregation_seconds' in e
    assert 'walls_surface_expiration_seconds' in e
    assert 'gamma_grid_scoring_seconds' in e
