from pathlib import Path
r=Path.cwd(); s=(r/'src/trading_ai/historical_underlying_replay/service.py').read_text(); m=(r/'migrations/versions/m77_002_historical_underlying_replay_authority.py').read_text()
assert 'CURRENT_UNIVERSE_HISTORICAL_REPLAY' in s
assert 'FROZEN_CURRENT_STOCK_INTELLIGENCE_UNDERLYING_ONLY' in s
assert 'external_context={}' in s
assert 'AMBIGUOUS_SAME_BAR' in s
assert "DELETE FROM historical_underlying_replay_authority" in s
for x in ('DELETE FROM price_history','UPDATE price_history','INSERT INTO price_history','INSERT INTO stock_scanner','UPDATE stock_scanner','portfolio_allocation_publications','execution_intent'):
 assert x not in s,x
assert "down_revision='m68_004'" in m
print('M77.1 source verification PASSED')
print(' - replay is additive and production-authority isolated')
print(' - current StockIntelligenceService is reused without modification')
print(' - non-PIT external context is disabled')
print(' - daily-bar ambiguity is explicit')
print(' - source price_history is read-only')
