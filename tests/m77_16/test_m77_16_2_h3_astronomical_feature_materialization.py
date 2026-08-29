from pathlib import Path
import json,py_compile
ROOT=Path(__file__).resolve().parents[2]
C=ROOT/"config/m77/m77_16_2_h3_feature_materialization.json"
R=ROOT/"scripts/run_m77_16_2_h3_astronomical_feature_materialization.py"
M=ROOT/"src/trading_ai/historical_underlying_replay/mundane_market_house_features.py"

def test_compile():
    py_compile.compile(str(R),doraise=True); py_compile.compile(str(M),doraise=True)

def test_external_lahiri_benchmark_frozen():
    x=json.loads(C.read_text())
    assert x["frozen_external_benchmarks"]["lahiri_ayanamsha_1792_05_17_deg"]==20.96
    assert x["frozen_external_benchmarks"]["lahiri_tolerance_deg"]==0.01

def test_feature_semantics_frozen():
    x=json.loads(C.read_text())
    f=x["feature_definition"]
    assert f["conjunction_orb_deg"]==3.0
    assert "TRANSITING_TRUE_NODE" in f["node_house_state"]
    assert "TRANSITING_LONGITUDE_OF_FIXED_HOUSE_LORD_PLANET" in f["node_lord_conjunction_state"]
    assert f["factor_combinations"] is False

def test_no_financial_outcomes():
    x=R.read_text()
    assert "FORWARD_RETURN" not in x
    assert "ABSOLUTE_RETURN" not in x
    assert "REALIZED_VOLATILITY" not in x

def test_isolation():
    x=R.read_text()
    assert "SessionLocal" not in x
    assert "from trading_ai.database" not in x
    assert '"production_authority_effect":False' in x
