from __future__ import annotations

from dataclasses import asdict
from typing import Any, Mapping

from .engine import AutomationObservabilityEngine
from .policy import AutomationObservabilityPolicy
from .profile import AutomationObservabilityResult


class AutomationObservabilityService:
    def __init__(
        self,
        policy: AutomationObservabilityPolicy | None = None,
    ) -> None:
        self.policy = policy or AutomationObservabilityPolicy()
        self.policy.validate()
        self.engine = AutomationObservabilityEngine(self.policy)

    def execute(
        self,
        portfolio_id: str,
        phase5_report: Mapping[str, Any],
        phase6_report: Mapping[str, Any],
    ) -> AutomationObservabilityResult:
        telemetry = self.engine.telemetry(
            portfolio_id,
            dict(phase5_report),
            dict(phase6_report),
        )
        checks = self.engine.checks(telemetry)
        incidents = self.engine.incidents(portfolio_id, checks)
        score = self.engine.health_score(checks)
        status = self.engine.overall_status(score)
        alert_summary = self.engine.alert_summary(incidents)
        recovery_actions = tuple(
            dict.fromkeys(row.recommended_action for row in incidents)
        )
        warnings = tuple(
            row.source_code
            for row in incidents
            if row.severity in {"HIGH", "MODERATE", "LOW"}
        )
        errors = tuple(
            row.source_code
            for row in incidents
            if row.severity == "CRITICAL"
        )
        return AutomationObservabilityResult(
            milestone=51,
            phase=7,
            portfolio_id=portfolio_id,
            overall_status=status,
            health_score=score,
            telemetry=asdict(telemetry),
            checks=tuple(asdict(row) for row in checks),
            incidents=tuple(asdict(row) for row in incidents),
            recovery_actions=recovery_actions,
            alert_summary=alert_summary,
            warnings=warnings,
            errors=errors,
            metadata={
                "environment": "PAPER",
                "live_trading_enabled": False,
                "incident_count": len(incidents),
            },
        )
