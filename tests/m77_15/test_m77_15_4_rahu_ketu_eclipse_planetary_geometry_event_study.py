from pathlib import Path
import csv,py_compile

ROOT=Path(__file__).resolve().parents[2]
R=ROOT/"scripts/run_m77_15_4_rahu_ketu_eclipse_planetary_geometry_event_study.py"
D=ROOT/"data/m77/m77_15_4_astronomical_event_registry_2000_2040.csv"

def test_compile():
    py_compile.compile(str(R),doraise=True)

def test_event_registry_present():
    with D.open() as f:
        rows=list(csv.DictReader(f))
    assert len(rows)>50
    families={r["event_family"] for r in rows}
    for f in ("SOLAR_ECLIPSE","LUNAR_ECLIPSE","JUPITER_SATURN_CONJUNCTION","JUPITER_RAHU_CONJUNCTION","SATURN_RAHU_CONJUNCTION"):
        assert f in families

def test_event_study_governance():
    x=R.read_text()
    assert '"event_study_only":True' in x
    assert '"daily_category_sweep":False' in x
    assert '"event_orb_retuning":False' in x
    assert '"event_window_retuning":False' in x
    assert '"factor_combinations":False' in x

def test_controls_and_multiplicity():
    x=R.read_text()
    assert "weekday_month_pit_regime_matched_controls" in x
    assert "circular_event_calendar_null" in x
    assert "BENJAMINI_HOCHBERG" in x

def test_no_production():
    x=R.read_text()
    assert '"production_authority_effect":False' in x
    assert '"automatic_promotion":False' in x
