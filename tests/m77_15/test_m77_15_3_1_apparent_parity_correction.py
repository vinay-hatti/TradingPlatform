from pathlib import Path
import py_compile

ROOT=Path(__file__).resolve().parents[2]
P=ROOT/"src/trading_ai/historical_underlying_replay/jpl_horizons_ephemeris.py"
R=ROOT/"scripts/run_m77_15_3_graha_state_major_transit_study.py"

def test_compile():
    py_compile.compile(str(P),doraise=True)
    py_compile.compile(str(R),doraise=True)

def test_horizons_observer_quantity_31():
    x=P.read_text()
    assert "EPHEM_TYPE" in x and "OBSERVER" in x
    assert "QUANTITIES" in x and "31" in x
    assert "fetch_geocentric_apparent_ecliptic_longitude" in x

def test_registry_certification_is_like_for_like():
    x=R.read_text()
    assert "registry_apparent_tropical_deg" in x
    assert "jpl_apparent_ecliptic_of_date_deg" in x
    assert "apparent_angular_error_deg" in x

def test_geometric_comparison_is_diagnostic_only():
    x=R.read_text()
    assert "geometric_vs_registry_diagnostic_error_deg" in x
