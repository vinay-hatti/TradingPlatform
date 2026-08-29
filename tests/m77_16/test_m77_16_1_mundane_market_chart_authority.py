from pathlib import Path
import json,py_compile

ROOT=Path(__file__).resolve().parents[2]
C=ROOT/"config/m77/m77_16_1_mundane_market_chart_authority.json"
R=ROOT/"scripts/run_m77_16_1_mundane_market_chart_authority.py"

def test_compile():
    py_compile.compile(str(R),doraise=True)

def test_reference_chart_frozen():
    x=json.loads(C.read_text())
    m=x["market_chart_authority"]
    assert m["reference_event"]["date"]=="1792-05-17"
    assert m["reference_event"]["time_local"]=="12:00:00"
    assert m["reference_event"]["location"]["name"]=="New York City"
    assert m["ayanamsha"]=="LAHIRI"
    assert m["house_system"]=="WHOLE_SIGN"
    assert m["node_type"]=="TRUE_NODE"

def test_no_chart_search():
    x=json.loads(C.read_text())
    g=x["governance"]
    assert g["automatic_chart_selection"] is False
    assert g["multiple_chart_search"] is False
    assert g["multiple_location_search"] is False
    assert g["multiple_house_system_search"] is False
    assert g["multiple_ayanamsha_search"] is False

def test_h3_scope_frozen():
    x=json.loads(C.read_text())
    h=x["h3_preregistration"]
    assert h["conjunction_orb_deg"]==3.0
    assert h["factor_combinations"] is False
    assert h["neighboring_orb_search"] is False
    assert h["posthoc_threshold_changes"] is False

def test_23_year_authority_preserved():
    x=json.loads(C.read_text())
    a=x["authority"]
    assert a["long_history_common_start"]=="2003-09-10"
    assert a["long_history_common_end"]=="2026-08-21"
    assert a["long_history_common_sessions"]==5773
    assert a["long_history_instruments"]["SPX"]["instrument"]=="SPY"
    assert a["long_history_instruments"]["NDX"]["instrument"]=="QQQ_LINEAGE"
    assert a["long_history_instruments"]["RUT"]["instrument"]=="IWM"

def test_no_production():
    x=R.read_text()
    assert "SessionLocal" not in x
    assert "from trading_ai.database" not in x
    assert '"production_authority_effect":False' in x
