from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
def test_replay_service_is_additive_and_isolated():
 s=(ROOT/'src/trading_ai/historical_underlying_replay/service.py').read_text()
 assert 'CURRENT_UNIVERSE_HISTORICAL_REPLAY' in s
 assert 'production_authority_effect' in s
 assert "external_context={}" in s
 for forbidden in ('UPDATE stock_scanner','INSERT INTO stock_scanner','DELETE FROM price_history','UPDATE price_history','INSERT INTO price_history','portfolio_allocation_publications','execution_intent'):
  assert forbidden not in s
def test_replay_governs_point_in_time_and_ambiguity():
 s=(ROOT/'src/trading_ai/historical_underlying_replay/service.py').read_text()
 assert "pos+1:pos+61" in s
 assert "history=rows[max(0,pos-749):pos+1]" in s
 assert 'AMBIGUOUS_SAME_BAR' in s
 assert 'SPY_DAILY_SESSIONS' in s
def test_migration_only_adds_replay_tables():
 s=(ROOT/'migrations/versions/m77_002_historical_underlying_replay_authority.py').read_text()
 assert "down_revision='m68_004'" in s
 assert s.count("op.create_table('historical_underlying_replay_") == 5
 assert 'alter_column' not in s and 'drop_column' not in s
