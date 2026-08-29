from pathlib import Path
import py_compile

R = Path("scripts/run_m77_19_1_multi_cadence_historical_reconstructibility_audit.py")

def test_compile():
    py_compile.compile(str(R), doraise=True)

def test_explicit_gate_key_mapping():
    x = R.read_text()
    assert '"pit": "pit_regime_runner_historical_range_capable"' in x
    assert 'gates[f"{kind}_replay_runner_historical_range_capable"]' not in x
