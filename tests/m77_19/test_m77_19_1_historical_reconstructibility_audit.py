from pathlib import Path
import json, py_compile

R = Path("scripts/run_m77_19_1_multi_cadence_historical_reconstructibility_audit.py")
C = Path("config/m77/m77_19_1_historical_reconstructibility_audit.json")

def test_compile():
    py_compile.compile(str(R), doraise=True)

def test_contract():
    x = json.loads(C.read_text())
    assert x["original_study_contract"]["M77_11_expected_symbols"] == 600
    assert x["original_study_contract"]["M77_12_expected_symbols"] == 603
    assert x["target_history"]["proxy_only_exact_replication"] is False

def test_governance():
    x = json.loads(C.read_text())["governance"]
    assert x["read_only"] is True
    assert x["automatic_replay_execution"] is False
    assert x["database_writes"] is False
    assert x["no_fabricated_pit_regimes"] is True
    assert x["production_authority_effect"] is False
