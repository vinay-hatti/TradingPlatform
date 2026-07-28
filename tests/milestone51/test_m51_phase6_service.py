from datetime import datetime, timezone

from trading_ai.paper_trading.automation_scheduler import (
    AutomationRunStateRepository,
    AutomationSchedulerService,
    ScheduledPhaseCommand,
)


def test_scheduler_executes_and_persists(tmp_path):
    repo = AutomationRunStateRepository(tmp_path / "state.json")
    service = AutomationSchedulerService(repo)
    result = service.execute(
        "PAPER-PRIMARY",
        "TEST",
        "RUN-1",
        [
            ScheduledPhaseCommand(
                phase=1,
                name="PASS",
                command=("python", "-c", "print('ok')"),
                retry_limit=0,
                timeout_seconds=30,
            )
        ],
        mode="DRY_RUN",
        now=datetime(2026, 7, 27, 14, 0, tzinfo=timezone.utc),
    )
    assert result.status == "PHASE6_SCHEDULED_RUN_COMPLETED"
    assert result.summary["completed"] == 1
    assert "RUN-1" in repo.existing_run_keys()


def test_required_failure_stops_following_phases(tmp_path):
    repo = AutomationRunStateRepository(tmp_path / "state.json")
    service = AutomationSchedulerService(repo)
    result = service.execute(
        "PAPER-PRIMARY",
        "TEST",
        "RUN-2",
        [
            ScheduledPhaseCommand(
                phase=1,
                name="FAIL",
                command=("python", "-c", "raise SystemExit(2)"),
                retry_limit=0,
                timeout_seconds=30,
            ),
            ScheduledPhaseCommand(
                phase=2,
                name="SHOULD_NOT_RUN",
                command=("python", "-c", "print('bad')"),
                retry_limit=0,
                timeout_seconds=30,
            ),
        ],
        mode="DRY_RUN",
        now=datetime(2026, 7, 27, 14, 0, tzinfo=timezone.utc),
    )
    assert result.status == "PHASE6_SCHEDULED_RUN_FAILED"
    assert len(result.executions) == 1
