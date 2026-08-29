from pathlib import Path
import json,py_compile

R=Path("scripts/run_m77_19_6_isolated_replay_engine_parity.py")
C=Path("config/m77/m77_19_6_isolated_replay_engine_parity.json")

def test_compile():
    py_compile.compile(str(R),doraise=True)

def test_exact_parity_policy():
    x=json.loads(C.read_text())["parity_policy"]
    assert x["direction_exact_required_pct"]==100.0
    assert x["overall_score_max_abs_error"]==1e-9
    assert x["confidence_max_abs_error"]==1e-9
    assert x["state_hash_exact_required"] is True
    assert x["deterministic_repeat_required"] is True

def test_no_writes():
    x=json.loads(C.read_text())["governance"]
    assert x["database_read_only"] is True
    assert x["database_writes"] is False
    assert x["production_price_history_writes"] is False
    assert x["production_authority_effect"] is False

def test_full_reconstruction_not_done_here():
    assert json.loads(C.read_text())["governance"]["full_long_history_reconstruction"] is False
