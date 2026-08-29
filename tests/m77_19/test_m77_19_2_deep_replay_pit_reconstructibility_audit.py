from pathlib import Path
import json, py_compile

R = Path("scripts/run_m77_19_2_deep_replay_pit_reconstructibility_audit.py")
C = Path("config/m77/m77_19_2_deep_replay_pit_reconstructibility_audit.json")

def test_compile():
    py_compile.compile(str(R), doraise=True)

def test_read_only():
    x = json.loads(C.read_text())["governance"]
    assert x["read_only"] is True
    assert x["automatic_replay_execution"] is False
    assert x["database_writes"] is False
    assert x["source_mutation"] is False
    assert x["production_authority_effect"] is False

def test_no_fabricated_pit():
    x = json.loads(C.read_text())["governance"]
    assert x["no_fabricated_pit_regimes"] is True

def test_target_history():
    x = json.loads(C.read_text())["target_history"]
    assert x["desired_start"] == "2003-09-10"
    assert x["desired_end"] == "2026-08-21"
    assert x["desired_sessions"] == 5773
