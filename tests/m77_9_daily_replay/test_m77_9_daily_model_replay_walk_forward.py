from pathlib import Path

def test_runner_governance():
 s=Path('scripts/run_m77_9_daily_model_replay.py').read_text(); assert "cadence='DAILY'" in s; assert 'RUN_M77_9_DAILY_MODEL_REPLAY' in s; assert 'SessionLocal' in s

def test_certification_horizons():
 s=Path('scripts/certify_m77_9_daily_walk_forward.py').read_text(); assert 'H=(5,10,20,40,60)' in s; assert 'FULL_YEARS=(2023,2024,2025)' in s

def test_no_production_promotion():
 s=Path('scripts/certify_m77_9_daily_walk_forward.py').read_text(); assert "'automatic_champion_promotion':False" in s; assert "'production_authority_effect':False" in s

def test_sessionlocal_import():
 for p in ('scripts/run_m77_9_daily_model_replay.py','scripts/certify_m77_9_daily_walk_forward.py'):
  s=Path(p).read_text(); assert 'from trading_ai.database.session import SessionLocal' in s; assert 'trading_ai.database import DATABASE_URL' not in s
