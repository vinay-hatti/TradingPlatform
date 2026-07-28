from trading_ai.paper_trading.automation_observability import (
    AutomationObservabilityService,
)


def test_failures_create_incidents_and_recovery_actions():
    phase5 = {
        "status": "PHASE5_AUTOMATION_BLOCKED",
        "consolidated_summary": {
            "phase2": {"active_orders": 1, "stale_orders": 2},
            "phase3": {"total_positions": 3, "exit_candidates": 1},
            "phase4": {
                "health_score": 55,
                "health_grade": "F",
                "risk_breach_count": 2,
                "daily_pnl": -5000,
                "net_liquidation_value": 100000,
            },
        },
    }
    phase6 = {
        "status": "PHASE6_SCHEDULED_RUN_FAILED",
        "summary": {
            "completed": 1,
            "failed": 2,
            "retried": 4,
        },
        "warnings": ["W1"],
        "errors": ["E1"],
    }
    result = AutomationObservabilityService().execute(
        "PAPER-PRIMARY", phase5, phase6
    )
    assert result.overall_status == "PHASE7_AUTOMATION_UNHEALTHY"
    codes = {row["source_code"] for row in result.incidents}
    assert "STALE_ORDER_COUNT" in codes
    assert "RISK_BREACH_COUNT" in codes
    assert "SCHEDULER_COMPLETED" in codes
    assert result.recovery_actions
