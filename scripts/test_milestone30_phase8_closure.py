from __future__ import annotations

from pathlib import Path


REQUIRED_MODULES = (
    "service_health_policy.py",
    "service_health_profile.py",
    "service_health_engine.py",
    "service_health_service.py",
    "runtime_health_registry.py",
    "resilience_policy.py",
    "resilience_profile.py",
    "retry_engine.py",
    "circuit_breaker_engine.py",
    "failure_isolation_engine.py",
    "resilience_execution_service.py",
    "recovery_policy.py",
    "recovery_profile.py",
    "service_restart_engine.py",
    "incident_engine.py",
    "recovery_workflow_engine.py",
    "watchdog_policy.py",
    "watchdog_profile.py",
    "health_alert_router.py",
    "incident_escalation_engine.py",
    "operational_watchdog_service.py",
    "operational_resilience_reporting.py",
    "operational_resilience_dashboard.py",
    "operational_resilience_cli.py",
)

REQUIRED_COMMANDS = (
    "operational-resilience-report",
    "operational-resilience-dashboard",
)

REQUIRED_REPORT_SECTIONS = (
    "Service Health, Heartbeats, and Dependency Readiness",
    "Retry, Circuit Breakers, and Failure Isolation",
    "Automatic Recovery, Service Restarts, and Recovery Audit",
    "Incidents, Health Alerts, and Escalations",
    "Operational Watchdog and Recovery Orchestration",
)


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    package = root / "src/trading_ai/operational_resilience"

    missing = [
        name for name in REQUIRED_MODULES
        if not (package / name).exists()
    ]
    assert not missing, f"Missing Phase 8 modules: {missing}"

    cli = (package / "operational_resilience_cli.py").read_text(
        encoding="utf-8"
    )
    for command in REQUIRED_COMMANDS:
        assert command in cli

    reporting = (
        package / "operational_resilience_reporting.py"
    ).read_text(encoding="utf-8")
    for section in REQUIRED_REPORT_SECTIONS:
        assert section in reporting

    status = (root / "updated_PROJECT_STATUS.md").read_text(
        encoding="utf-8"
    )
    assert "Milestone 30 — Phase 8" in status
    assert "Status: COMPLETE" in status
    assert "Operational Resilience" in status
    assert "Step 5" in status

    print("All Milestone 30 Phase 8 closure assertions passed.")


if __name__ == "__main__":
    main()
