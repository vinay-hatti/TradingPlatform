from pathlib import Path
import json,py_compile
ROOT=Path(__file__).resolve().parents[2]
R=ROOT/"scripts/run_m77_17_lunar_survivor_long_history_replication.py"
C=ROOT/"config/m77/m77_17_lunar_survivor_long_history_replication.json"

def test_compile(): py_compile.compile(str(R),doraise=True)

def test_frozen_survivor_exact():
    x=json.loads(C.read_text())["lunar_survivor"]["source_hypothesis"]
    assert x["target"]=="NDX"
    assert x["hypothesis"]=="FIRST_QUARTER_WINDOW"
    assert x["horizon_sessions"]==10
    assert x["outcome"]=="ABSOLUTE_RETURN"
    assert x["prediction"]=="SUPPRESSED_10D_ABSOLUTE_MOVE"

def test_23_year_authority():
    x=json.loads(C.read_text())["lunar_survivor"]["long_history_authority"]
    assert x["common_start"]=="2003-09-10"
    assert x["common_end"]=="2026-08-21"
    assert x["expected_sessions"]==5773

def test_primary_is_qqq_lineage():
    x=json.loads(C.read_text())["lunar_survivor"]
    assert x["primary_replication"]["target"]=="NDX"
    assert x["primary_replication"]["instrument"]=="QQQ_LINEAGE"

def test_no_lunar_researcher_degrees_of_freedom():
    x=json.loads(C.read_text())["lunar_survivor"]
    assert x["event_definition"]["posthoc_window_change"] is False
    assert x["source_hypothesis"]["horizon_sessions"]==10

def test_failure_terminates_shadow_by_policy():
    x=json.loads(C.read_text())["lunar_survivor"]["decision_policy"]
    assert x["if_primary_qqq_fails"]=="TERMINATE_M77_14_PROSPECTIVE_SHADOW_AND_CLOSE_LUNAR_RESEARCH"

def test_vedic_closed():
    x=json.loads(C.read_text())["closure"]
    assert x["M77_15"]["disposition"]=="CLOSED_UNSUPPORTED"
    assert x["M77_16"]["disposition"]=="CLOSED_UNSUPPORTED"

def test_no_production():
    x=R.read_text()
    assert "SessionLocal" not in x
    assert "from trading_ai.database" not in x
    assert '"production_authority_effect":False' in x
