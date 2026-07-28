from trading_ai.paper_trading.automation_observability import (
    AutomationObservabilityService,
)


def test_healthy_automation_has_no_incidents():
    phase5 = {
        "status": "PHASE5_AUTOMATION_READY",
        "consolidated_summary": {
            "phase2": {"active_orders": 1, "stale_orders": 0},
            "phase3": {"total_positions": 1, "exit_candidates": 0},
            "phase4": {
                "health_score": 95,
                "health_grade": "A",
                "risk_breach_count": 0,
                "daily_pnl": 100,
                "net_liquidation_value": 100000,
            },
        },
    }
    phase6 = {
        "status": "PHASE6_SCHEDULED_RUN_COMPLETED",
        "summary": {
            "completed": 3,
            "failed": 0,
            "retried": 0,
        },
        "warnings": [],
        "errors": [],
    }
    result = AutomationObservabilityService().execute(
        "PAPER-PRIMARY", phase5, phase6
    )
    assert result.overall_status == "PHASE7_AUTOMATION_HEALTHY"
    assert result.health_score == 100
    assert result.incidents == ()
