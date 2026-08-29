from pathlib import Path
import json,py_compile

ROOT=Path(__file__).resolve().parents[2]
R=ROOT/"scripts/run_m77_15_6_3_long_history_tradable_proxy_authority.py"
C=ROOT/"config/m77/m77_15_6_3_tradable_proxy_authority.json"

def test_compile():
    py_compile.compile(str(R),doraise=True)

def test_explicit_proxy_mapping():
    x=json.loads(C.read_text())
    assert x["targets"]["SPX"]["research_instrument"]=="SPY"
    assert x["targets"]["NDX"]["research_instrument"]=="QQQ"
    assert x["targets"]["RUT"]["research_instrument"]=="IWM"

def test_proxy_identity_never_hidden():
    x=R.read_text()
    for token in ("research_target","research_instrument","authority_type","proxy_for"):
        assert token in x
    assert "LONG_HISTORY_TRADABLE_PROXY" in x

def test_isolation():
    x=R.read_text()
    assert "SessionLocal" not in x
    assert "from trading_ai.database" not in x
    assert '"production_price_history_writes":False' in x
    assert '"production_authority_effect":False' in x

def test_no_fallback_semantics():
    x=json.loads(C.read_text())
    assert x["fallback_substitution"] is False
    assert x["proxy_may_be_represented_as_index"] is False
    assert x["canonical_index_authority_overwrite"] is False

def test_iwm_target_specific_start_gate():
    x=json.loads(C.read_text())
    assert x["targets"]["RUT"]["certification_start_no_later_than"]=="2000-06-01"
