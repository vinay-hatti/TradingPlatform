from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
RUN=ROOT/"scripts/run_m77_10_monthly_model_replay.py"
CERT=ROOT/"scripts/certify_m77_10_monthly_walk_forward.py"

def test_monthly_replay_is_explicit():
    s=RUN.read_text()
    assert '"--cadence","MONTHLY"' in s
    assert "RUN_M77_10_MONTHLY_MODEL_REPLAY" in s

def test_sessionlocal_convention():
    assert "from trading_ai.database.session import SessionLocal" in RUN.read_text()

def test_monthly_horizons():
    assert "HORIZONS=(60,120,180,252)" in CERT.read_text()

def test_governance():
    s=RUN.read_text()+CERT.read_text()
    assert '"production_authority_effect":False' in s
    assert "existing_weekly_m77_mutation" in s
    assert "existing_daily_m77_mutation" in s

def test_walk_forward_is_pre_holdout():
    s=CERT.read_text()
    assert 'tr0=[x for x in obs if x["year"]<y]' in s
    assert "selection_uses_only_pre_holdout_data" in s
