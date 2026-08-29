from pathlib import Path
import json,py_compile
ROOT=Path(__file__).resolve().parents[2]
R=ROOT/"scripts/run_m77_17_2_astrology_research_closure.py"
C=ROOT/"config/m77/m77_17_2_astrology_research_closure.json"

def test_compile(): py_compile.compile(str(R),doraise=True)
def test_all_astrology_branches_closed():
    x=json.loads(C.read_text())
    assert x["closure"]["M77_14"]["disposition"]=="CLOSED_UNSUPPORTED_LONG_HISTORY_REPLICATION_FAILURE"
    assert x["closure"]["M77_15"]["disposition"]=="CLOSED_UNSUPPORTED"
    assert x["closure"]["M77_16"]["disposition"]=="CLOSED_UNSUPPORTED"
def test_artifacts_preserved():
    x=json.loads(C.read_text())["retirement"]
    assert x["preserve_historical_artifacts"] is True
    assert x["delete_research_artifacts"] is False
    assert x["delete_logs"] is False
    assert x["delete_data"] is False
def test_no_production_mutation():
    x=json.loads(C.read_text())
    r=x["retirement"]
    assert r["production_model_change"] is False
    assert r["production_ranking_change"] is False
    assert r["production_decision_change"] is False
    assert x["governance"]["database_writes"] is False
    assert x["governance"]["production_authority_effect"] is False
def test_fail_closed_evidence_gate():
    x=R.read_text()
    assert 'primary_replication_pass") is not False' in x
    assert "TERMINATE_M77_14_PROSPECTIVE_SHADOW_AND_CLOSE_LUNAR_RESEARCH" in x
