from pathlib import Path
import json,py_compile
ROOT=Path(__file__).resolve().parents[2]
B=ROOT/"scripts/build_m77_17_1_lunar_feature_authority.py"
R=ROOT/"scripts/run_m77_17_lunar_survivor_long_history_replication.py"
C=ROOT/"config/m77/m77_17_lunar_survivor_long_history_replication.json"

def test_compile():
    py_compile.compile(str(B),doraise=True); py_compile.compile(str(R),doraise=True)

def test_reconstruction_source_is_certified_panchanga():
    x=B.read_text()
    assert 'data/m77/m77_15_2_panchanga_daily_2000_2040.csv' in x
    assert "moon_sidereal_deg" in x and "sun_sidereal_deg" in x

def test_frozen_window_unchanged():
    x=json.loads(C.read_text())["lunar_survivor"]["event_definition"]
    assert x["phase_angle_center_deg"]==90.0
    assert x["half_width_deg"]==22.5
    assert x["posthoc_window_change"] is False

def test_no_financial_outcomes_in_builder():
    x=B.read_text()
    for s in ("FORWARD_RETURN","ABSOLUTE_RETURN","REALIZED_VOLATILITY","price_history"):
        assert s not in x
