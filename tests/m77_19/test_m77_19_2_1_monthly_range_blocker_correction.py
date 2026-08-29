from pathlib import Path
import py_compile

R = Path("scripts/run_m77_19_2_deep_replay_pit_reconstructibility_audit.py")

def test_compile():
    py_compile.compile(str(R), doraise=True)

def test_monthly_range_failure_is_a_blocker():
    x = R.read_text()
    assert 'blockers.append("MONTHLY_RUNNER_NEEDS_HISTORICAL_DATE_PARAMETERIZATION")' in x

def test_next_step_includes_monthly():
    x = R.read_text()
    assert "BUILD_M77_19_3_DATE_PARAMETERIZED_ISOLATED_DAILY_MONTHLY_PIT_HARNESS" in x

def test_isolation_contract_includes_monthly():
    x = R.read_text()
    assert '"date_parameterized_monthly_replay": True' in x
