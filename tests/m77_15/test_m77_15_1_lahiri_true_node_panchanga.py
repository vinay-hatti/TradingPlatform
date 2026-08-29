from pathlib import Path
import py_compile,json
ROOT=Path(__file__).resolve().parents[2]
F=ROOT/"src/trading_ai/historical_underlying_replay/vedic_astronomy_foundation.py"
R=ROOT/"scripts/run_m77_15_1_lahiri_true_node_panchanga.py"
def test_compile():
    py_compile.compile(str(F),doraise=True); py_compile.compile(str(R),doraise=True)
def test_lahiri_authority():
    x=R.read_text(); assert "SWISS_EPHEMERIS_2.10.03_MONTHLY_BENCHMARK_INTERPOLATION_2000_2040" in x; assert "AYAN_TOL_DEG=0.01" in x
def test_true_node_authority():
    x=R.read_text(); assert "NASA_JPL_HORIZONS_MOON_STATE_VECTOR_OSCULATING_ASCENDING_NODE" in x; assert "NODE_TOL_DEG=1.0" in x
def test_panchanga_scope():
    x=F.read_text()
    for v in ("rashi","nakshatra","tithi","yoga","karana","true_node_from_state","ketu_from_rahu"): assert f"def {v}" in x
def test_fail_closed():
    x=R.read_text(); assert "Sidereal materialization blocked: parity not certified" in x
def test_no_financial_backtest():
    x=R.read_text(); assert '"financial_backtesting":False' in x; assert '"production_authority_effect":False' in x

def test_project_root_path_contract():
    x=F.read_text()
    assert 'ROOT=Path(__file__).resolve().parents[3]' in x
    assert 'BENCH=ROOT/"config/m77/m77_15_1_lahiri_monthly_benchmarks_2000_2040.json"' in x

def test_json_serialization_is_atomic_and_validated():
    x=R.read_text()
    assert "def write_json_atomic" in x
    assert "json.loads(tmp.read_text())" in x
    assert "tmp.replace(path)" in x

def test_materialize_repairs_legacy_literal_newline_suffix():
    x=R.read_text()
    assert "def load_certification_json" in x
    assert "while cleaned.endswith" in x
    assert "cert=load_certification_json(CERT)" in x
