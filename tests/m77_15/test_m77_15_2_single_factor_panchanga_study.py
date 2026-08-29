from pathlib import Path
import csv,json,py_compile
ROOT=Path(__file__).resolve().parents[2]
R=ROOT/"scripts/run_m77_15_2_single_factor_panchanga_study.py"
D=ROOT/"data/m77/m77_15_2_panchanga_daily_2000_2040.csv"

def test_compile():
    py_compile.compile(str(R),doraise=True)

def test_registry_present_and_large():
    with D.open() as f:
        rows=list(csv.DictReader(f))
    assert len(rows)>14000

def test_frozen_single_factor_scope():
    x=R.read_text()
    for v in ("TITHI","PAKSHA","MOON_NAKSHATRA","MOON_RASHI","YOGA","KARANA","VARA"): assert v in x
    assert '"factor_combinations":False' in x
    assert '"neighboring_category_search":False' in x

def test_calendar_control():
    x=R.read_text()
    assert "weekday_month_pit_regime_matched_controls" in x
    assert 'r["factor"]!="VARA"' in x
    assert "CALENDAR_CONTROL_ONLY" in x

def test_outcomes():
    x=R.read_text()
    for v in ("FORWARD_RETURN","ABSOLUTE_RETURN","REALIZED_VOLATILITY","MAX_ADVERSE_EXCURSION","MAX_FAVORABLE_EXCURSION","TURNING_POINT_3_SESSION","REGIME_TRANSITION"): assert v in x

def test_boundary_exclusion():
    x=R.read_text()
    assert "BOUNDARY_EXCLUSION_DEG=0.10" in x

def test_no_production():
    x=R.read_text()
    assert '"production_authority_effect":False' in x
    assert '"automatic_promotion":False' in x

def test_study_artifact_atomic_json_writer():
    x=R.read_text()
    assert "def write_json_atomic" in x
    assert "json.loads(tmp.read_text())" in x
    assert "tmp.replace(path)" in x
    assert "write_json_atomic(OUT,out)" in x
