from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
RUN=ROOT/"scripts/run_m77_8_daily_pit_replay_authority.py"

def s(): return RUN.read_text()

def test_governance_is_read_only_and_additive():
    x=s()
    assert '"database_writes": False' in x
    assert '"database_migrations": False' in x
    assert '"production_authority_effect": False' in x
    assert '"existing_weekly_m77_mutation": False' in x

def test_sessionlocal_verified_path():
    x=s()
    assert "from trading_ai.database.session import SessionLocal" in x
    assert "DATABASE_URL" not in x
    assert "database.database import engine" not in x

def test_daily_horizons_and_warmup_are_binding():
    x=s()
    assert "DAILY_HORIZONS = (5, 10, 20, 40, 60)" in x
    assert "MIN_WARMUP_SESSIONS = 252" in x

def test_uses_existing_pit_regime_service_not_weekly_forward_fill():
    x=s()
    assert "HistoricalRegimeAuthorityService" in x
    assert "build_authority(regime_dates)" in x
    assert "forward-fill" not in x.lower()

def test_frozen_weekly_parity_is_fail_closed():
    x=s()
    assert "compare_snapshot" in x
    assert "frozen_weekly_regime_parity" in x
    assert "does not exactly reproduce frozen M77.3 weekly snapshots" in x

def test_adjusted_polygon_source_gate_is_required():
    x=s()
    assert "adjusted=True" in x
    assert "POLYGON_ADJUSTED_AGGREGATES" in x
    assert "adjusted-price provenance gate failed" in x

def test_no_mutating_sql():
    x=s().upper()
    assert "INSERT INTO" not in x
    assert "UPDATE " not in x
    assert "DELETE FROM" not in x

def test_confluence_remains_blocked():
    x=s()
    assert '"multi_cadence_confluence_ready": False' in x
    assert "BUILD_DAILY_MODEL_REPLAY_AND_WALK_FORWARD_CERTIFICATION" in x
