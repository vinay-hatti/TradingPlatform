from pathlib import Path
import json,py_compile
ROOT=Path(__file__).resolve().parents[2]
R=ROOT/"scripts/run_m77_18_historical_depth_replication_authority_audit.py"
C=ROOT/"config/m77/m77_18_historical_depth_audit.json"

def test_compile(): py_compile.compile(str(R),doraise=True)
def test_read_only_governance():
    x=json.loads(C.read_text())["governance"]
    assert x["database_writes"] is False
    assert x["production_authority_effect"] is False
    assert x["source_files_mutated"] is False
    assert x["reports_mutated"] is False
    assert x["historical_artifacts_deleted"] is False
def test_5773_authority():
    x=json.loads(C.read_text())["long_history_authority"]
    assert x["common_start"]=="2003-09-10"
    assert x["common_end"]=="2026-08-21"
    assert x["expected_common_sessions"]==5773
    assert x["targets"]=={"SPX":"SPY","NDX":"QQQ_LINEAGE","RUT":"IWM"}
def test_classification_policy():
    x=json.loads(C.read_text())
    assert "SHORT_HISTORY_EMPIRICAL_REPLICATION_REQUIRED" in x["classification_policy"]
    assert "LONG_HISTORY_ALREADY_CERTIFIED" in x["classification_policy"]
    assert "DESCRIPTIVE_ONLY" in x["classification_policy"]
def test_closed_astrology_branches():
    x=json.loads(C.read_text())["known_closed_branches"]
    assert x["M77.14"]=="CLOSED_UNSUPPORTED_LONG_HISTORY_REPLICATION_FAILURE"
    assert x["M77.15"]=="CLOSED_UNSUPPORTED"
    assert x["M77.16"]=="CLOSED_UNSUPPORTED"
