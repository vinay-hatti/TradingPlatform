from pathlib import Path
import json,py_compile

ROOT=Path(__file__).resolve().parents[2]
C=ROOT/"config/m77/m77_15_6_5_material_long_history_proxy_certification.json"
R=ROOT/"scripts/certify_m77_15_6_5_material_long_history_proxy_authority.py"

def test_compile():
    py_compile.compile(str(R),doraise=True)

def test_frozen_material_authority_contract():
    x=json.loads(C.read_text())
    assert x["authority_type"]=="MATERIAL_LONG_HISTORY_TRADABLE_PROXY"
    assert x["certified_common_start"]=="2003-09-10"
    assert x["minimum_common_sessions"]==5700

def test_explicit_proxy_mapping():
    x=json.loads(C.read_text())
    assert x["targets"]["SPX"]["research_instrument"]=="SPY"
    assert x["targets"]["NDX"]["research_instrument"]=="QQQ_LINEAGE"
    assert x["targets"]["RUT"]["research_instrument"]=="IWM"

def test_cross_authority_promotion_governance():
    x=R.read_text()
    assert '"proxy_only_survivor_may_not_advance":True' in x
    assert '"canonical_recent_index_confirmation_required":True' in x
    assert '"same_effect_direction_required_across_authorities":True' in x

def test_frozen_eras():
    x=R.read_text()
    for token in ("2003-09-10","2008-12-31","2009-01-01","2014-12-31","2015-01-01","2020-12-31","2021-01-01"):
        assert token in x
    assert '"posthoc_era_changes_prohibited":True' in x

def test_isolation():
    x=R.read_text()
    assert "SessionLocal" not in x
    assert "from trading_ai.database" not in x
    assert '"production_price_history_writes":False' in x
    assert '"production_authority_effect":False' in x
