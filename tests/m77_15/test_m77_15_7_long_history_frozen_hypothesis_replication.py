from pathlib import Path
import json,py_compile

ROOT=Path(__file__).resolve().parents[2]
R=ROOT/"scripts/run_m77_15_7_long_history_frozen_hypothesis_replication.py"
C=ROOT/"config/m77/m77_15_7_long_history_replication.json"

def test_compile():
    py_compile.compile(str(R),doraise=True)

def test_certified_authority_required():
    x=R.read_text()
    assert "certified_for_m77_15_7_long_history_replication" in x
    assert "M77.15.7 blocked" in x

def test_frozen_hypothesis_families():
    x=R.read_text()
    assert "PANCHANGA_FACTORS" in x
    assert "GRAHA_FACTORS" in x
    assert "EVENT_FAMILIES" in x
    assert '"frozen_hypotheses_only":True' in x
    assert '"new_hypothesis_search":False' in x

def test_no_historical_pit_fabrication():
    x=json.loads(C.read_text())
    assert x["pit_regime_control_in_long_history"] is False

def test_frozen_eras():
    x=json.loads(C.read_text())
    assert x["frozen_eras"]==[
        ["2003-09-10","2008-12-31"],
        ["2009-01-01","2014-12-31"],
        ["2015-01-01","2020-12-31"],
        ["2021-01-01","2026-08-21"],
    ]

def test_cross_authority_promotion_required():
    x=R.read_text()
    assert '"proxy_only_survivor_may_not_advance":True' in x
    assert '"recent_canonical_confirmation_required":True' in x
    assert '"same_effect_direction_required":True' in x

def test_isolation():
    x=R.read_text()
    assert "SessionLocal" not in x
    assert "from trading_ai.database" not in x
    assert '"database_writes":False' in x
    assert '"production_authority_effect":False' in x
