from trading_ai.paper_trading.automation_observability import (
    AutomationObservabilityService,
    render_observability_markdown,
)


def test_observability_report_renders():
    phase5 = {
        "status": "PHASE5_AUTOMATION_READY",
        "consolidated_summary": {
            "phase2": {"active_orders": 0, "stale_orders": 0},
            "phase3": {"total_positions": 0, "exit_candidates": 0},
            "phase4": {
                "health_score": 90,
                "health_grade": "A",
                "risk_breach_count": 0,
                "daily_pnl": 0,
                "net_liquidation_value": 100000,
            },
        },
    }
    phase6 = {
        "status": "PHASE6_SCHEDULED_RUN_COMPLETED",
        "summary": {"completed": 3, "failed": 0, "retried": 0},
        "warnings": [],
        "errors": [],
    }
    result = AutomationObservabilityService().execute(
        "PAPER-PRIMARY", phase5, phase6
    )
    markdown = render_observability_markdown(result.to_dict())
    assert "Automation Observability" in markdown
    assert "Health Checks" in markdown
    assert "Net liquidation value" in markdown
