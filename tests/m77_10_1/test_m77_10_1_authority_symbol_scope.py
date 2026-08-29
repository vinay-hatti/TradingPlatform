from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
RUN=ROOT/"scripts/run_m77_10_monthly_model_replay.py"

def s(): return RUN.read_text()

def test_no_summary_rows_assumption():
    assert 'authority["rows"]' not in s()

def test_persisted_authority_symbol_scope():
    x=s()
    assert "discover_authority_table" in x
    assert "WHERE disposition='ELIGIBLE'" in x

def test_materialization_summary_not_used_as_rows():
    x=s()
    assert "summary=HistoricalUnderlyingReplayService(s).materialize_authority()" in x

def test_sessionlocal():
    assert "from trading_ai.database.session import SessionLocal" in s()

def test_governance_preserved():
    x=s()
    assert '"production_authority_effect":False' in x
    assert '"existing_weekly_m77_mutation":False' in x
    assert '"existing_daily_m77_mutation":False' in x

def test_monthly_cadence_preserved():
    assert '"--cadence","MONTHLY"' in s()
