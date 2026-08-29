from pathlib import Path
import json,py_compile
ROOT=Path(__file__).resolve().parents[2]
R=ROOT/"scripts/run_m77_16_3_h3_long_history_financial_study.py"
C=ROOT/"config/m77/m77_16_3_h3_long_history_financial_study.json"

def test_compile(): py_compile.compile(str(R),doraise=True)

def test_23_year_authority():
    x=json.loads(C.read_text())
    assert x["authority"]["common_start"]=="2003-09-10"
    assert x["authority"]["expected_common_sessions"]==5773
    assert x["authority"]["targets"]["SPX"]["instrument"]=="SPY"
    assert x["authority"]["targets"]["NDX"]["instrument"]=="QQQ_LINEAGE"
    assert x["authority"]["targets"]["RUT"]["instrument"]=="IWM"

def test_exact_h3_states():
    x=json.loads(C.read_text())
    assert len(x["states"])==8
    assert "rahu_in_5th_house" in x["states"]
    assert "ketu_conjunct_11th_lord" in x["states"]

def test_predictions_frozen():
    x=json.loads(C.read_text())
    assert x["predictions"]["ABSOLUTE_RETURN"]=="POSITIVE"
    assert x["predictions"]["REALIZED_VOLATILITY"]=="POSITIVE"
    assert x["predictions"]["MAX_ADVERSE_EXCURSION"]=="MORE_NEGATIVE"

def test_no_combinations_or_orb_search():
    x=json.loads(C.read_text())
    assert x["factor_combinations"] is False
    assert x["posthoc_orb_search"] is False

def test_isolation():
    x=R.read_text()
    assert "SessionLocal" not in x
    assert "from trading_ai.database" not in x
    assert '"production_authority_effect":False' in x
