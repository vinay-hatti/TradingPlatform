from pathlib import Path
import py_compile
ROOT=Path(__file__).resolve().parents[2]
R=ROOT/"scripts/run_m77_14_3_prospective_lunar_volatility_shadow.py"
P=ROOT/"scripts/patch_m77_14_3_1_combined_orchestrator.py"

def test_compile():
    py_compile.compile(str(R),doraise=True)
    py_compile.compile(str(P),doraise=True)

def test_partial_launch_episode():
    x=R.read_text()
    assert 'LAUNCH_PARTIAL_EPISODE_ID = "FIRST_QUARTER_WINDOW:2026-08-19"' in x
    assert "PARTIAL_LAUNCH_EPISODE" in x
    assert "counts_toward_review_gate" in x

def test_eligible_only_gate():
    x=R.read_text()
    assert "eligible_completed" in x
    assert "len(eligible_completed) >= MIN_COMPLETED_EPISODES_FOR_REVIEW" in x

def test_orchestration_patch():
    x=P.read_text()
    assert "run_combined_forward_shadow.sh" in x
    assert "run_m77_14_3_prospective_lunar_volatility_shadow.py cycle" in x
    assert "DEGRADED M77.14.3 lunar shadow failed" in x
