from trading_ai.paper_trading.automation_recovery import AutomationRecoveryEngine


def test_failed_phase_builds_ordered_recovery_plan():
    engine = AutomationRecoveryEngine()
    report = {
        "run_key": "RUN-1",
        "executions": [
            {"phase": 2, "status": "COMPLETED", "metadata": {"required": True}},
            {"phase": 4, "status": "FAILED", "metadata": {"required": True}},
            {"phase": 5, "status": "SKIPPED", "metadata": {"required": True}},
        ],
    }
    checkpoints = engine.checkpoints(report)
    actions = engine.plan(checkpoints)
    assert actions[0].phase == 4
    assert any(row.action_code == "REVALIDATE_CONTROL_PLANE" for row in actions)
    assert any(row.action_code == "VERIFY_OBSERVABILITY" for row in actions)
