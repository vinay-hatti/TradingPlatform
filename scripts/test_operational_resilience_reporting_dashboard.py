from __future__ import annotations

import json
from pathlib import Path
import tempfile

from trading_ai.operational_resilience.operational_resilience_dashboard import (
    OperationalResilienceDashboardBuilder,
)
from trading_ai.operational_resilience.operational_resilience_reporting import (
    OperationalResilienceReportBuilder,
)


def _write(path: Path, payload: dict) -> None:
    path.write_text(
        json.dumps(payload, indent=2) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        health = root / "health.json"
        resilience = root / "resilience.json"
        recovery = root / "recovery.json"
        watchdog = root / "watchdog.json"

        _write(health, {
            "registries": {
                "paper-runtime": {
                    "registry_id": "paper-runtime",
                    "environment": "paper",
                    "overall_status": "DEGRADED",
                    "ready": False,
                    "healthy": False,
                    "score": 62.5,
                    "service_count": 2,
                    "failed_service_count": 1,
                    "updated_at": "2026-07-16T20:00:00+00:00",
                    "services": [{
                        "service_name": "broker-adapter",
                        "instance_id": "broker-1",
                        "status": "FAILED",
                        "ready": False,
                        "healthy": False,
                        "score": 0,
                        "heartbeat_age_seconds": 180,
                    }],
                }
            }
        })
        _write(resilience, {
            "circuits": {
                "broker": {
                    "dependency_name": "broker",
                    "state": "OPEN",
                    "failure_count": 5,
                    "success_count": 0,
                    "version": 6,
                }
            },
            "bulkheads": {
                "broker": {
                    "dependency_name": "broker",
                    "active_calls": 0,
                    "queued_calls": 0,
                    "rejected_calls": 3,
                    "completed_calls": 10,
                }
            },
        })
        _write(recovery, {
            "workflows": {
                "wf-1": {
                    "workflow_id": "wf-1",
                    "service_name": "broker-adapter",
                    "environment": "paper",
                    "status": "FAILED",
                    "current_step": "INCIDENT_OPENED",
                    "attempt_count": 3,
                    "failure_reason": "RECOVERY_ATTEMPTS_EXHAUSTED",
                }
            },
            "incidents": {
                "incident-1": {
                    "incident_id": "incident-1",
                    "service_name": "broker-adapter",
                    "environment": "paper",
                    "severity": "CRITICAL",
                    "status": "OPEN",
                    "assigned_role": "ON_CALL_OPERATIONS",
                }
            },
            "audits": [],
            "restarts": {},
        })
        _write(watchdog, {
            "alerts": {
                "alert-1": {
                    "alert_id": "alert-1",
                    "service_name": "broker-adapter",
                    "environment": "paper",
                    "severity": "CRITICAL",
                    "status": "PENDING",
                    "occurrence_count": 2,
                    "incident_id": "incident-1",
                }
            },
            "escalations": {
                "escalation-1": {
                    "escalation_id": "escalation-1",
                    "incident_id": "incident-1",
                    "level": 1,
                    "target_role": "ON_CALL_OPERATIONS",
                    "status": "PENDING",
                }
            },
            "cycles": {
                "cycle-1": {
                    "cycle_id": "cycle-1",
                    "environment": "paper",
                    "sequence_number": 1,
                    "status": "COMPLETED",
                    "recommendation": "RECOVERY_REQUIRED",
                    "alert_count": 1,
                    "incident_count": 1,
                    "recovery_count": 1,
                    "started_at": "2026-07-16T20:01:00+00:00",
                }
            },
        })

        paths = {
            "health_registry_path": health,
            "resilience_state_path": resilience,
            "recovery_state_path": recovery,
            "watchdog_state_path": watchdog,
        }
        builder = OperationalResilienceReportBuilder()
        payload = builder.build_payload(
            environment="paper",
            **paths,
        )
        assert payload["summary"]["runtime_status"] == "DEGRADED"
        assert payload["summary"]["open_circuit_count"] == 1
        assert payload["summary"]["open_incident_count"] == 1
        assert (
            payload["summary"]["critical_open_incident_count"] == 1
        )
        assert (
            payload["summary"]["latest_watchdog_recommendation"]
            == "RECOVERY_REQUIRED"
        )

        html = builder.build_html(payload)
        for section in (
            "Operational Resilience Reporting",
            "Service Health, Heartbeats, and Dependency Readiness",
            "Retry, Circuit Breakers, and Failure Isolation",
            "Automatic Recovery, Service Restarts, and Recovery Audit",
            "Incidents, Health Alerts, and Escalations",
            "Operational Watchdog and Recovery Orchestration",
        ):
            assert section in html

        report_path = builder.write_report(
            output=root / "report.html",
            environment="paper",
            **paths,
        )
        assert report_path.exists()

        dashboard = OperationalResilienceDashboardBuilder().build(
            environment="paper",
            **paths,
        )
        for key in (
            "summary",
            "health",
            "resilience",
            "recovery",
            "incidents",
            "alerts",
            "escalations",
            "watchdog",
        ):
            assert key in dashboard
        assert dashboard["incidents"]["open_count"] == 1
        assert dashboard["watchdog"]["latest_recommendation"] == (
            "RECOVERY_REQUIRED"
        )

        dashboard_path = (
            OperationalResilienceDashboardBuilder().write(
                output=root / "dashboard.json",
                environment="paper",
                **paths,
            )
        )
        assert dashboard_path.exists()

    print(
        "All operational-resilience reporting and dashboard assertions passed."
    )


if __name__ == "__main__":
    main()
