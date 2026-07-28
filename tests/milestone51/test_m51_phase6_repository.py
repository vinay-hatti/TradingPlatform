from trading_ai.paper_trading.automation_scheduler import (
    AutomationRunStateRepository,
)


def test_run_state_is_restart_safe(tmp_path):
    repo = AutomationRunStateRepository(tmp_path / "state.json")
    assert repo.existing_run_keys() == ()
    repo.save_run("RUN-1", {"status": "COMPLETED"})
    assert repo.existing_run_keys() == ("RUN-1",)
    assert repo.load()["runs"]["RUN-1"]["status"] == "COMPLETED"
