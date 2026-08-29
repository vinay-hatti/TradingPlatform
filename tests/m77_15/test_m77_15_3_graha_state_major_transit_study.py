from pathlib import Path
import csv,py_compile
ROOT=Path(__file__).resolve().parents[2]
R=ROOT/"scripts/run_m77_15_3_graha_state_major_transit_study.py"
D=ROOT/"data/m77/m77_15_3_graha_state_daily_2000_2040.csv"

def test_compile():
    py_compile.compile(str(R),doraise=True)

def test_registry():
    with D.open() as f:rows=list(csv.DictReader(f))
    assert len(rows)>14000
    for k in ("mercury_retrograde","jupiter_station_window_3d","saturn_sun_proximity_8deg","jupiter_rashi","saturn_nakshatra","rahu_rashi","rahu_rashi_ingress_window_3d"):
        assert k in rows[0]

def test_certification_required():
    x=R.read_text()
    assert "JPL_APPARENT_ECLIPTIC_PARITY_BEFORE_FINANCIAL_STUDY" in x
    assert "require_cert()" in x
    assert "JPL_MAX_ERROR_DEG=0.10" in x

def test_single_factor_governance():
    x=R.read_text()
    assert '"factor_combinations":False' in x
    assert '"neighboring_threshold_search":False' in x
    assert "GEOMETRIC_RESEARCH_PROXY_NOT_TRADITIONAL_COMBUSTION_AUTHORITY" in x

def test_no_production():
    x=R.read_text()
    assert '"production_authority_effect":False' in x
    assert '"automatic_promotion":False' in x

def test_apparent_to_apparent_parity_contract():
    x=R.read_text()
    assert "fetch_geocentric_apparent_ecliptic_longitude" in x
    assert "SWISS_APPARENT_GEOCENTRIC_VS_JPL_OBSERVER_QUANTITY_31_APPARENT_ECLIPTIC_OF_DATE" in x
    assert "geometric_vs_registry_diagnostic_error_deg" in x
