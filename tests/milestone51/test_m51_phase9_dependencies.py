from trading_ai.paper_trading.operational_readiness import DependencyValidator


def test_missing_phase_report_fails():
    controls = DependencyValidator().validate({}, (1,))
    assert controls[0].status == "FAIL"


def test_healthy_phase_reports_pass():
    reports = {
        1: {"status": "PHASE1_AUTOMATION_READY"},
        2: {"status": "NO_ACTIVE_ORDERS"},
    }
    controls = DependencyValidator().validate(reports, (1, 2))
    assert all(row.status == "PASS" for row in controls)
