from trading_ai.paper_trading.automation_recovery import (
    AutomationRecoveryService,
    render_recovery_markdown,
)


def test_service_reports_recovery_plan():
    scheduler = {
        "run_key": "RUN-1",
        "status": "PHASE6_SCHEDULED_RUN_FAILED",
        "executions": [
            {"phase": 4, "status": "FAILED", "metadata": {"required": True}}
        ],
    }
    result = AutomationRecoveryService().execute(
        "PAPER-PRIMARY", scheduler, mode="ANALYZE"
    )
    assert result.status == "PHASE8_RECOVERY_PLAN_READY"
    text = render_recovery_markdown(result.to_dict())
    assert "Automation Recovery" in text
    assert "Recovery Actions" in text
