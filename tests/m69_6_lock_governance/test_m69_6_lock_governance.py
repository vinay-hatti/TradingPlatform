from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
COMMON = ROOT / "scripts/m69_6_scheduled/common.sh"

def test_critical_jobs_wait():
    s = COMMON.read_text()
    assert "morning_full_ingestion|end_of_day_ingestion" in s
    assert 'LOCK_POLICY="${LOCK_POLICY:-WAIT}"' in s
    assert 'LOCK_WAIT_SECONDS="${LOCK_WAIT_SECONDS:-2700}"' in s

def test_noncritical_jobs_skip():
    s = COMMON.read_text()
    assert 'LOCK_POLICY="${LOCK_POLICY:-SKIP}"' in s
    assert "SKIPPED_OVERLAP" in s

def test_wait_is_observable():
    s = COMMON.read_text()
    for token in ("WAITING_FOR_LOCK","STILL_WAITING_FOR_LOCK","LOCK_ACQUIRED_AFTER_WAIT","LOCK_WAIT_TIMEOUT"):
        assert token in s

def test_timeout_is_failure():
    s = COMMON.read_text()
    assert "exit 75" in s

def test_stale_lock_recovery_preserved():
    s = COMMON.read_text()
    assert "STALE_LOCK_RECOVERY" in s
    assert "kill -0" in s

def test_cleanup_only_removes_owned_lock():
    s = COMMON.read_text()
    assert 'if [[ "${owner_pid}" == "$$" ]]' in s
