from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
RUN=ROOT/"scripts/run_m77_10_monthly_model_replay.py"; CERT=ROOT/"scripts/certify_m77_10_monthly_walk_forward.py"
def test_no_nonexistent_service_method():
    assert ".run_baseline(" not in RUN.read_text()
def test_reuses_proven_m77_1_cli():
    s=RUN.read_text(); assert "run_m77_1_cli" in s; assert '"run-baseline"' in s; assert '"--cadence","MONTHLY"' in s
def test_long_horizons_not_assumed_in_m77_1_outcome_json():
    s=CERT.read_text(); assert "return_120d_pct" not in s; assert "return_180d_pct" not in s; assert "return_252d_pct" not in s
def test_long_horizons_from_price_history():
    s=CERT.read_text(); assert "price_history" in s; assert "HORIZONS=(60,120,180,252)" in s
def test_exact_pit_regime_binding():
    s=CERT.read_text(); assert "m77_8_daily_pit_regime_snapshots.json" in s; assert "missing_pit_regime_predictions" in s
def test_governance():
    s=RUN.read_text()+CERT.read_text(); assert "production_authority_effect" in s; assert "existing_weekly_m77_mutation" in s; assert "existing_daily_m77_mutation" in s
