from pathlib import Path
import json,py_compile
ROOT=Path(__file__).resolve().parents[2]
R=ROOT/"scripts/run_m77_18_1_semantic_replication_backlog_refinement.py"
C=ROOT/"config/m77/m77_18_1_semantic_replication_backlog.json"

def test_compile(): py_compile.compile(str(R),doraise=True)
def test_p0_families():
    x=json.loads(C.read_text())["candidate_families"]
    assert x["M77.3"]["priority"]=="P0"
    assert x["M77.11"]["priority"]=="P0"
    assert x["M77.12"]["priority"]=="P0"
def test_closed_astrology_excluded():
    x=json.loads(C.read_text())["hard_exclusions"]["closed_astrology"]
    assert x==["M77.14","M77.15","M77.16","M77.17"]
def test_outcome_probability_conditional():
    x=json.loads(C.read_text())["candidate_families"]["M77.0_OUTCOME_PROBABILITY"]
    assert x["priority"]=="P1_CONDITIONAL"
    assert "empirical calibration" in x["condition"]
def test_read_only():
    x=json.loads(C.read_text())["governance"]
    assert x["read_only"] is True
    assert x["database_writes"] is False
    assert x["source_mutation"] is False
    assert x["production_authority_effect"] is False
