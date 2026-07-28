from trading_ai.paper_trading.automation_control_plane import (
    AutomationControlPlaneEngine,
)


def test_missing_required_phase_is_detected():
    statuses = AutomationControlPlaneEngine().validate_dependencies(
        {1: {"status": "READY"}, 2: None, 3: {}, 4: {}}
    )
    assert statuses[1].status == "MISSING_REQUIRED"


def test_all_reports_are_ready():
    reports = {
        phase: {"status": "READY", "warnings": [], "errors": []}
        for phase in range(1, 5)
    }
    statuses = AutomationControlPlaneEngine().validate_dependencies(reports)
    assert all(row.status == "READY" for row in statuses)
