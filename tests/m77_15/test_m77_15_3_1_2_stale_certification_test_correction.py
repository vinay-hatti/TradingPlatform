from pathlib import Path
import py_compile

ROOT=Path(__file__).resolve().parents[2]
R=ROOT/"scripts/run_m77_15_3_graha_state_major_transit_study.py"
T=ROOT/"tests/m77_15/test_m77_15_3_graha_state_major_transit_study.py"

def test_compile():
    py_compile.compile(str(R),doraise=True)
    py_compile.compile(str(T),doraise=True)

def test_test_suite_matches_runtime_contract():
    runtime=R.read_text()
    tests=T.read_text()
    token="JPL_APPARENT_ECLIPTIC_PARITY_BEFORE_FINANCIAL_STUDY"
    assert token in runtime
    assert token in tests
    assert 'JPL_PARITY_BEFORE_FINANCIAL_STUDY" in x' not in tests
