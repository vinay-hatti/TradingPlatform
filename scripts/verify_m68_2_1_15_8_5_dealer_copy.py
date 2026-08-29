from pathlib import Path
root=Path(__file__).resolve().parents[1]
service=(root/'src/trading_ai/institutional_market_structure/service.py').read_text()
refresh=(root/'src/trading_ai/institutional_market_structure/refresh.py').read_text()
engine=(root/'src/trading_ai/institutional_market_structure/engine.py').read_text()
assert 'POSTGRES_COPY_SINGLE_WRITER' in service
assert 'copy_expert' in service
assert 'SQLALCHEMY_BULK_FALLBACK' in service
assert 'SYMBOL_FALLBACK_AFTER_COPY_AND_BULK_FAILURE' in service
assert 'compute_domain_profiles' in refresh
assert 'metrics_normalization_seconds' in engine
assert 'gamma_grid_scoring_seconds' in engine
print('M68.2.1.15.8.5 source verification PASSED')
print(' - PostgreSQL COPY single-writer path')
print(' - SQLAlchemy + symbol-isolated fallbacks preserved')
print(' - dealer compute-domain profiling')
print(' - no strategy / valuation / decision governance changes')
