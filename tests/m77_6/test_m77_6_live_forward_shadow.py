from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
def src(): return (ROOT/'scripts/run_m77_6_live_forward_shadow.py').read_text()
def test_is_research_only_and_no_production_mutation():
    s=src(); assert "production_authority_effect':False" in s or "'production_authority_effect':False" in s; assert 'automatic_champion_promotion' in s; assert 'institutional_option' not in s.lower(); assert 'portfolio_' not in s.lower()
def test_uses_verified_database_convention():
    s=src(); assert 'from trading_ai.database.session import SessionLocal' in s; assert 'DATABASE_URL' not in s
def test_prospective_start_is_frozen():
    s=src(); assert 'START=date(2026,8,18)' in s; assert 'Prospective capture cannot predate' in s
def test_policy_is_fail_closed():
    s=src(); assert 'RESEARCH_SHADOW_ONLY' in s; assert 'ABSTAIN_FROM_BEARISH_CHALLENGER_SUPPORT_DO_NOT_INVERT' in s; assert "score_mutation" in s and "threshold_mutation" in s
def test_idempotent_signal_fingerprint():
    s=src(); assert 'signal_fingerprint' in s; assert "SELECT 1 FROM m77_shadow_signals" in s
def test_outcomes_require_future_spy_sessions():
    s=src(); assert "symbol='SPY' AND date>:d" in s; assert "status='OPEN'" in s
def test_migration_is_research_tables_only():
    s=(ROOT/'alembic/versions/m77_003_live_forward_shadow_intelligence.py').read_text(); assert "down_revision='m77_002'" in s; assert "m77_shadow_signals" in s and "m77_shadow_outcomes" in s; assert 'stock_scanner_' not in s
