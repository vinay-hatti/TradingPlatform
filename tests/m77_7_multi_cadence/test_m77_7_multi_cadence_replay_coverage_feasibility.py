from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
RUN=ROOT/"scripts/run_m77_7_multi_cadence_replay_coverage_feasibility.py"

def s(): return RUN.read_text()

def test_read_only_governance():
    x=s()
    assert '"database_writes": False' in x
    assert '"database_migrations": False' in x
    assert '"production_authority_effect": False' in x
    assert '"existing_weekly_m77_mutation": False' in x

def test_verified_sessionlocal_import():
    x=s()
    assert "from trading_ai.database.session import SessionLocal" in x
    assert "DATABASE_URL" not in x

def test_daily_weekly_monthly_contract():
    x=s()
    assert "DAILY_HORIZONS = (5, 10, 20, 40, 60)" in x
    assert "WEEKLY_REFERENCE_HORIZONS = (20, 40, 60)" in x
    assert "MONTHLY_HORIZONS = (60, 120, 180, 252)" in x
    assert "PRESERVE_EXISTING_FROZEN_M77_BASELINE" in x

def test_daily_pit_regime_gap_is_explicit():
    x=s()
    assert "DAILY_POINT_IN_TIME_REGIME_AUTHORITY_NOT_MATERIALIZED" in x
    assert "Do not forward-fill weekly" in x

def test_survivorship_limitation_explicit():
    x=s()
    assert "CURRENT_UNIVERSE_SURVIVORSHIP_BIAS" in x
    assert "survivorship-bias-free" in x

def test_no_database_mutation_sql():
    x=s().upper()
    assert "INSERT INTO" not in x
    assert "UPDATE " not in x
    assert "DELETE FROM" not in x

def test_multi_cadence_not_premature():
    x=s()
    assert '"multi_cadence_confluence_ready": False' in x
    assert "Validate daily and monthly authorities independently" in x
