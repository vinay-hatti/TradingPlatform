from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .operational_resilience_reporting import (
    OperationalResilienceReportBuilder,
)


class OperationalResilienceDashboardBuilder:
    """Create a dashboard-ready JSON payload without replacing UI code."""

    def __init__(self) -> None:
        self.report_builder = OperationalResilienceReportBuilder()

    def build(
        self,
        *,
        environment: str,
        **paths: Any,
    ) -> dict[str, Any]:
        payload = self.report_builder.build_payload(
            environment=environment,
            **paths,
        )
        summary = payload["summary"]
        return {
            "schema_version": payload["schema_version"],
            "generated_at": payload["generated_at"],
            "environment": environment,
            "summary": summary,
            "health": {
                "overall": payload["runtime_health"],
                "services": payload["runtime_health"].get(
                    "services", []
                ),
            },
            "resilience": {
                "circuits": payload["circuits"],
                "bulkheads": payload["bulkheads"],
            },
            "recovery": {
                "workflows": payload["recovery_workflows"],
                "failed_count": summary["failed_recovery_count"],
            },
            "incidents": {
                "items": payload["incidents"],
                "open_count": summary["open_incident_count"],
                "critical_open_count": (
                    summary["critical_open_incident_count"]
                ),
            },
            "alerts": {
                "items": payload["alerts"],
                "count": summary["alert_count"],
            },
            "escalations": {
                "items": payload["escalations"],
                "count": summary["escalation_count"],
            },
            "watchdog": {
                "cycles": payload["watchdog_cycles"],
                "latest_status": summary["latest_watchdog_status"],
                "latest_recommendation": (
                    summary["latest_watchdog_recommendation"]
                ),
            },
        }

    def write(
        self,
        *,
        output: str | Path,
        environment: str,
        **paths: Any,
    ) -> Path:
        payload = self.build(environment=environment, **paths)
        target = Path(output)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return target
