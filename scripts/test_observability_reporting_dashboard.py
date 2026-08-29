from __future__ import annotations
import argparse
from pathlib import Path
import tempfile
from trading_ai.observability.observability_cli import register_observability_commands
from trading_ai.observability.observability_dashboard import ObservabilityDashboardBuilder
from trading_ai.observability.observability_reporting import ObservabilityReportBuilder
from trading_ai.observability.slo_profile import (
    ErrorBudgetEvaluation, ObservabilityAlert, RetentionResult, SLOEvaluation
)

def main():
    slo = SLOEvaluation(
        slo_id="orders", service_name="order-management", environment="paper",
        indicator_type="AVAILABILITY", target=0.99, observed=0.98,
        compliant=False, sample_count=100, good_events=98, total_events=100,
        window_seconds=3600, recommendation="SLO_VIOLATED",
    )
    budget = ErrorBudgetEvaluation(
        slo_id="orders", allowed_bad_fraction=0.01,
        observed_bad_fraction=0.02, consumed_fraction=2.0,
        remaining_fraction=0.0, burn_rate=2.0, exhausted=True,
        fast_burn=False, slow_burn=False,
        recommendation="FREEZE_RISKY_CHANGES",
    )
    alert = ObservabilityAlert(
        alert_id="obs-alert-1", rule_id="orders-budget",
        service_name="order-management", environment="paper",
        severity="CRITICAL", status="OPEN",
        summary="Error budget exhausted", fingerprint="fp-1",
    )
    retention = RetentionResult(
        telemetry_type="TRACE", scanned=10, retained=8, deleted=2,
        archived=2, compliant=True, recommendation="RETENTION_ENFORCED",
    )
    html = ObservabilityReportBuilder().build(
        slos=(slo,), budgets=(budget,), alerts=(alert,),
        retention=(retention,),
    )
    for heading in ObservabilityReportBuilder.SECTIONS:
        assert heading in html
    assert "Production Observability Report" in html
    assert "SLO_VIOLATED" in html
    dashboard = ObservabilityDashboardBuilder().build(
        slos=(slo,), budgets=(budget,), alerts=(alert,),
        retention=(retention,),
    )
    assert dashboard["summary"]["slo_violations"] == 1
    assert dashboard["summary"]["exhausted_budgets"] == 1
    assert dashboard["summary"]["open_alerts"] == 1
    assert dashboard["summary"]["retention_deleted"] == 2
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command")
    register_observability_commands(subparsers)
    assert callable(parser.parse_args(["observability-report"]).func)
    assert callable(parser.parse_args(["observability-dashboard"]).func)
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        assert ObservabilityReportBuilder().write(root / "report.html", slos=(slo,)).exists()
        assert ObservabilityDashboardBuilder().write(root / "dashboard.json", slos=(slo,)).exists()
    print("All observability reporting, dashboard, and CLI integration assertions passed.")

if __name__ == "__main__":
    main()
