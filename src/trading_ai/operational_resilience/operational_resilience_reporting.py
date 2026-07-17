from __future__ import annotations

from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from html import escape
import json
from pathlib import Path
from typing import Any


def _json_safe(value: Any) -> Any:
    if is_dataclass(value):
        return _json_safe(asdict(value))
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(item) for item in value]
    if isinstance(value, (datetime, Path)):
        return str(value)
    return value


def _load(path: str | Path) -> dict[str, Any]:
    target = Path(path)
    if not target.exists():
        return {}
    return json.loads(target.read_text(encoding="utf-8"))


def _rows(items: list[dict[str, Any]], columns: tuple[str, ...]) -> str:
    if not items:
        return (
            f'<tr><td colspan="{len(columns)}">'
            "No persisted records available.</td></tr>"
        )
    rendered = []
    for item in items:
        rendered.append(
            "<tr>"
            + "".join(
                f"<td>{escape(str(item.get(column, '')))}</td>"
                for column in columns
            )
            + "</tr>"
        )
    return "\n".join(rendered)


class OperationalResilienceReportBuilder:
    """Build an audit-ready HTML report from Phase 8 repositories."""

    def build_payload(
        self,
        *,
        environment: str,
        health_registry_path: str | Path = (
            "data/operational_resilience/runtime_health_registry.json"
        ),
        resilience_state_path: str | Path = (
            "data/operational_resilience/resilience_state.json"
        ),
        recovery_state_path: str | Path = (
            "data/operational_resilience/recovery_state.json"
        ),
        watchdog_state_path: str | Path = (
            "data/operational_resilience/watchdog_state.json"
        ),
    ) -> dict[str, Any]:
        health = _load(health_registry_path)
        resilience = _load(resilience_state_path)
        recovery = _load(recovery_state_path)
        watchdog = _load(watchdog_state_path)

        registries = [
            item
            for item in health.get("registries", {}).values()
            if item.get("environment") == environment
        ]
        latest_health = max(
            registries,
            key=lambda item: item.get("updated_at", ""),
            default={},
        )

        cycles = [
            item
            for item in watchdog.get("cycles", {}).values()
            if item.get("environment") == environment
        ]
        latest_cycle = max(
            cycles,
            key=lambda item: (
                item.get("started_at", ""),
                item.get("sequence_number", 0),
            ),
            default={},
        )

        incidents = [
            item
            for item in recovery.get("incidents", {}).values()
            if item.get("environment") == environment
        ]
        open_incidents = [
            item for item in incidents
            if item.get("status") != "RESOLVED"
        ]
        workflows = [
            item
            for item in recovery.get("workflows", {}).values()
            if item.get("environment") == environment
        ]
        alerts = [
            item
            for item in watchdog.get("alerts", {}).values()
            if item.get("environment") == environment
        ]
        escalations = list(
            watchdog.get("escalations", {}).values()
        )
        circuits = list(
            resilience.get("circuits", {}).values()
        )
        bulkheads = list(
            resilience.get("bulkheads", {}).values()
        )

        return {
            "schema_version": "1.0",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "environment": environment,
            "summary": {
                "runtime_status": latest_health.get(
                    "overall_status", "UNKNOWN"
                ),
                "runtime_ready": latest_health.get("ready", False),
                "runtime_healthy": latest_health.get("healthy", False),
                "runtime_score": latest_health.get("score", 0.0),
                "service_count": latest_health.get(
                    "service_count", 0
                ),
                "failed_service_count": latest_health.get(
                    "failed_service_count", 0
                ),
                "open_circuit_count": sum(
                    item.get("state") == "OPEN"
                    for item in circuits
                ),
                "active_bulkhead_calls": sum(
                    int(item.get("active_calls", 0))
                    for item in bulkheads
                ),
                "rejected_bulkhead_calls": sum(
                    int(item.get("rejected_calls", 0))
                    for item in bulkheads
                ),
                "recovery_workflow_count": len(workflows),
                "failed_recovery_count": sum(
                    item.get("status") == "FAILED"
                    for item in workflows
                ),
                "open_incident_count": len(open_incidents),
                "critical_open_incident_count": sum(
                    item.get("severity") == "CRITICAL"
                    for item in open_incidents
                ),
                "alert_count": len(alerts),
                "escalation_count": len(escalations),
                "latest_watchdog_status": latest_cycle.get(
                    "status", "UNKNOWN"
                ),
                "latest_watchdog_recommendation": latest_cycle.get(
                    "recommendation", "UNKNOWN"
                ),
            },
            "runtime_health": latest_health,
            "circuits": circuits,
            "bulkheads": bulkheads,
            "recovery_workflows": workflows,
            "incidents": incidents,
            "alerts": alerts,
            "escalations": escalations,
            "watchdog_cycles": cycles,
        }

    def build_html(self, payload: dict[str, Any]) -> str:
        summary = payload["summary"]
        runtime = payload.get("runtime_health", {})
        services = runtime.get("services", [])
        circuits = payload.get("circuits", [])
        bulkheads = payload.get("bulkheads", [])
        workflows = payload.get("recovery_workflows", [])
        incidents = payload.get("incidents", [])
        alerts = payload.get("alerts", [])
        escalations = payload.get("escalations", [])
        cycles = payload.get("watchdog_cycles", [])

        cards = "".join(
            (
                '<div class="card">'
                f"<div class=\"label\">{escape(label)}</div>"
                f"<div class=\"value\">{escape(str(value))}</div>"
                "</div>"
            )
            for label, value in (
                ("Runtime Status", summary["runtime_status"]),
                ("Runtime Score", summary["runtime_score"]),
                ("Failed Services", summary["failed_service_count"]),
                ("Open Circuits", summary["open_circuit_count"]),
                ("Open Incidents", summary["open_incident_count"]),
                (
                    "Critical Incidents",
                    summary["critical_open_incident_count"],
                ),
                ("Alerts", summary["alert_count"]),
                (
                    "Watchdog",
                    summary["latest_watchdog_recommendation"],
                ),
            )
        )

        return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Operational Resilience Report</title>
<style>
body {{ font-family: Arial, sans-serif; margin: 24px; color: #1f2937; }}
h1, h2 {{ color: #111827; }}
.subtitle {{ color: #6b7280; margin-bottom: 20px; }}
.cards {{ display: grid; grid-template-columns: repeat(4, 1fr);
          gap: 12px; margin-bottom: 24px; }}
.card {{ border: 1px solid #d1d5db; border-radius: 8px; padding: 12px; }}
.label {{ color: #6b7280; font-size: 12px; }}
.value {{ font-size: 22px; font-weight: bold; margin-top: 6px; }}
table {{ width: 100%; border-collapse: collapse; margin-bottom: 24px; }}
th, td {{ border: 1px solid #d1d5db; padding: 8px; text-align: left; }}
th {{ background: #f3f4f6; }}
code {{ white-space: pre-wrap; }}
</style>
</head>
<body>
<h1>Operational Resilience Reporting</h1>
<div class="subtitle">
Environment: {escape(payload["environment"])} |
Generated: {escape(payload["generated_at"])}
</div>
<div class="cards">{cards}</div>

<h2>Service Health, Heartbeats, and Dependency Readiness</h2>
<table>
<tr><th>Service</th><th>Instance</th><th>Status</th><th>Ready</th>
<th>Healthy</th><th>Score</th><th>Heartbeat Age</th></tr>
{_rows(services, ("service_name", "instance_id", "status", "ready",
                  "healthy", "score", "heartbeat_age_seconds"))}
</table>

<h2>Retry, Circuit Breakers, and Failure Isolation</h2>
<table>
<tr><th>Dependency</th><th>State</th><th>Failures</th>
<th>Successes</th><th>Version</th></tr>
{_rows(circuits, ("dependency_name", "state", "failure_count",
                  "success_count", "version"))}
</table>
<table>
<tr><th>Dependency</th><th>Active</th><th>Queued</th>
<th>Rejected</th><th>Completed</th></tr>
{_rows(bulkheads, ("dependency_name", "active_calls", "queued_calls",
                   "rejected_calls", "completed_calls"))}
</table>

<h2>Automatic Recovery, Service Restarts, and Recovery Audit</h2>
<table>
<tr><th>Workflow</th><th>Service</th><th>Status</th><th>Step</th>
<th>Attempts</th><th>Failure</th></tr>
{_rows(workflows, ("workflow_id", "service_name", "status",
                   "current_step", "attempt_count", "failure_reason"))}
</table>

<h2>Incidents, Health Alerts, and Escalations</h2>
<table>
<tr><th>Incident</th><th>Service</th><th>Severity</th><th>Status</th>
<th>Assigned Role</th></tr>
{_rows(incidents, ("incident_id", "service_name", "severity",
                   "status", "assigned_role"))}
</table>
<table>
<tr><th>Alert</th><th>Service</th><th>Severity</th><th>Status</th>
<th>Occurrences</th><th>Incident</th></tr>
{_rows(alerts, ("alert_id", "service_name", "severity", "status",
                "occurrence_count", "incident_id"))}
</table>
<table>
<tr><th>Escalation</th><th>Incident</th><th>Level</th>
<th>Target</th><th>Status</th></tr>
{_rows(escalations, ("escalation_id", "incident_id", "level",
                     "target_role", "status"))}
</table>

<h2>Operational Watchdog and Recovery Orchestration</h2>
<table>
<tr><th>Cycle</th><th>Sequence</th><th>Status</th>
<th>Recommendation</th><th>Alerts</th><th>Incidents</th>
<th>Recoveries</th></tr>
{_rows(cycles, ("cycle_id", "sequence_number", "status",
                "recommendation", "alert_count", "incident_count",
                "recovery_count"))}
</table>
</body>
</html>"""

    def write_report(
        self,
        *,
        output: str | Path,
        environment: str,
        **paths: Any,
    ) -> Path:
        payload = self.build_payload(environment=environment, **paths)
        target = Path(output)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            self.build_html(payload),
            encoding="utf-8",
        )
        return target
