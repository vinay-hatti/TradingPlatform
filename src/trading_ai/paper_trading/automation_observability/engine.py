from __future__ import annotations

import hashlib
from dataclasses import asdict
from typing import Any, Iterable

from .policy import AutomationObservabilityPolicy
from .profile import (
    AutomationHealthCheck,
    AutomationIncident,
    AutomationTelemetrySnapshot,
)


def _stable_incident_id(portfolio_id: str, code: str) -> str:
    digest = hashlib.sha256(f"{portfolio_id}|{code}".encode()).hexdigest()[:20]
    return f"M51-INC-{digest.upper()}"


class AutomationObservabilityEngine:
    def __init__(
        self,
        policy: AutomationObservabilityPolicy | None = None,
    ) -> None:
        self.policy = policy or AutomationObservabilityPolicy()
        self.policy.validate()

    def telemetry(
        self,
        portfolio_id: str,
        phase5_report: dict[str, Any],
        phase6_report: dict[str, Any],
    ) -> AutomationTelemetrySnapshot:
        summary5 = phase5_report.get("consolidated_summary") or {}
        p2 = summary5.get("phase2") or {}
        p3 = summary5.get("phase3") or {}
        p4 = summary5.get("phase4") or {}
        summary6 = phase6_report.get("summary") or {}

        return AutomationTelemetrySnapshot(
            portfolio_id=portfolio_id,
            scheduler_status=str(phase6_report.get("status") or "UNKNOWN"),
            control_plane_status=str(phase5_report.get("status") or "UNKNOWN"),
            portfolio_health_score=float(p4.get("health_score", 0.0) or 0.0),
            portfolio_health_grade=str(p4.get("health_grade") or "UNKNOWN"),
            risk_breach_count=int(p4.get("risk_breach_count", 0) or 0),
            cycle_error_count=len(phase6_report.get("errors") or ()),
            cycle_warning_count=len(phase6_report.get("warnings") or ()),
            completed_phases=int(summary6.get("completed", 0) or 0),
            failed_phases=int(summary6.get("failed", 0) or 0),
            retried_phases=int(summary6.get("retried", 0) or 0),
            active_orders=int(p2.get("active_orders", 0) or 0),
            stale_orders=int(p2.get("stale_orders", 0) or 0),
            open_positions=int(p3.get("total_positions", 0) or 0),
            exit_candidates=int(p3.get("exit_candidates", 0) or 0),
            daily_pnl=float(p4.get("daily_pnl", 0.0) or 0.0),
            net_liquidation_value=float(
                p4.get("net_liquidation_value", 0.0) or 0.0
            ),
            metadata={
                "paper_only": True,
                "live_trading_enabled": False,
            },
        )

    def checks(
        self,
        telemetry: AutomationTelemetrySnapshot,
    ) -> tuple[AutomationHealthCheck, ...]:
        checks: list[AutomationHealthCheck] = []

        def add(code, component, ok, severity, message, actual, expected):
            checks.append(
                AutomationHealthCheck(
                    code=code,
                    component=component,
                    status="PASS" if ok else "FAIL",
                    severity="INFO" if ok else severity,
                    message=message,
                    actual=actual,
                    expected=expected,
                )
            )

        add(
            "PORTFOLIO_HEALTH",
            "PORTFOLIO",
            telemetry.portfolio_health_score
            >= self.policy.minimum_portfolio_health_score,
            "HIGH",
            "portfolio health score meets minimum",
            telemetry.portfolio_health_score,
            self.policy.minimum_portfolio_health_score,
        )
        add(
            "RISK_BREACH_COUNT",
            "PORTFOLIO",
            telemetry.risk_breach_count
            <= self.policy.maximum_risk_breaches,
            "CRITICAL",
            "portfolio risk breach count is within limit",
            telemetry.risk_breach_count,
            self.policy.maximum_risk_breaches,
        )
        add(
            "STALE_ORDER_COUNT",
            "ORDER_LIFECYCLE",
            telemetry.stale_orders <= self.policy.maximum_stale_orders,
            "HIGH",
            "stale broker order count is within limit",
            telemetry.stale_orders,
            self.policy.maximum_stale_orders,
        )
        add(
            "FAILED_PHASE_COUNT",
            "SCHEDULER",
            telemetry.failed_phases <= self.policy.maximum_failed_phases,
            "CRITICAL",
            "scheduled phase failure count is within limit",
            telemetry.failed_phases,
            self.policy.maximum_failed_phases,
        )
        add(
            "CYCLE_ERROR_COUNT",
            "SCHEDULER",
            telemetry.cycle_error_count <= self.policy.maximum_cycle_errors,
            "CRITICAL",
            "scheduled cycle error count is within limit",
            telemetry.cycle_error_count,
            self.policy.maximum_cycle_errors,
        )
        add(
            "CYCLE_WARNING_COUNT",
            "SCHEDULER",
            telemetry.cycle_warning_count <= self.policy.maximum_cycle_warnings,
            "MODERATE",
            "scheduled cycle warning count is within limit",
            telemetry.cycle_warning_count,
            self.policy.maximum_cycle_warnings,
        )
        add(
            "RETRY_PRESSURE",
            "SCHEDULER",
            telemetry.retried_phases <= self.policy.maximum_retried_phases,
            "MODERATE",
            "phase retry count is within limit",
            telemetry.retried_phases,
            self.policy.maximum_retried_phases,
        )
        daily_loss_pct = (
            0.0
            if telemetry.net_liquidation_value <= 0
            else abs(min(0.0, telemetry.daily_pnl))
            / telemetry.net_liquidation_value
            * 100.0
        )
        add(
            "DAILY_LOSS",
            "PORTFOLIO",
            daily_loss_pct <= self.policy.critical_daily_loss_pct,
            "CRITICAL",
            "daily loss is within limit",
            round(daily_loss_pct, 6),
            self.policy.critical_daily_loss_pct,
        )
        add(
            "CONTROL_PLANE_READY",
            "CONTROL_PLANE",
            telemetry.control_plane_status
            not in {"PHASE5_AUTOMATION_BLOCKED", "UNKNOWN"},
            "CRITICAL",
            "control plane is operational",
            telemetry.control_plane_status,
            "READY_OR_AUTHORIZED",
        )
        add(
            "SCHEDULER_COMPLETED",
            "SCHEDULER",
            telemetry.scheduler_status
            not in {
                "PHASE6_SCHEDULED_RUN_BLOCKED",
                "PHASE6_SCHEDULED_RUN_FAILED",
                "UNKNOWN",
            },
            "CRITICAL",
            "scheduler completed without blocking failure",
            telemetry.scheduler_status,
            "COMPLETED",
        )
        return tuple(checks)

    def incidents(
        self,
        portfolio_id: str,
        checks: Iterable[AutomationHealthCheck],
    ) -> tuple[AutomationIncident, ...]:
        actions = {
            "PORTFOLIO_HEALTH": "Review Phase 4 recommendations and reduce risk.",
            "RISK_BREACH_COUNT": "Block new entries and remediate portfolio breaches.",
            "STALE_ORDER_COUNT": "Run Phase 2 CANCEL_STALE with exact confirmation.",
            "FAILED_PHASE_COUNT": "Inspect Phase 6 stderr and rerun failed phase.",
            "CYCLE_ERROR_COUNT": "Resolve scheduler errors before next cycle.",
            "CYCLE_WARNING_COUNT": "Review accumulated warnings and data freshness.",
            "RETRY_PRESSURE": "Investigate provider, broker, or dependency instability.",
            "DAILY_LOSS": "Activate defensive mode and suspend new entries.",
            "CONTROL_PLANE_READY": "Resolve Phase 5 control-plane blocking conditions.",
            "SCHEDULER_COMPLETED": "Review Phase 6 run state and failed execution.",
        }
        categories = {
            "PORTFOLIO_HEALTH": "PORTFOLIO_RISK",
            "RISK_BREACH_COUNT": "PORTFOLIO_RISK",
            "STALE_ORDER_COUNT": "BROKER_LIFECYCLE",
            "FAILED_PHASE_COUNT": "AUTOMATION_FAILURE",
            "CYCLE_ERROR_COUNT": "AUTOMATION_FAILURE",
            "CYCLE_WARNING_COUNT": "AUTOMATION_DEGRADATION",
            "RETRY_PRESSURE": "DEPENDENCY_INSTABILITY",
            "DAILY_LOSS": "PORTFOLIO_LOSS",
            "CONTROL_PLANE_READY": "CONTROL_PLANE",
            "SCHEDULER_COMPLETED": "SCHEDULER",
        }
        incidents: list[AutomationIncident] = []
        for check in checks:
            if check.status == "PASS":
                continue
            incidents.append(
                AutomationIncident(
                    incident_id=_stable_incident_id(portfolio_id, check.code),
                    category=categories.get(check.code, "AUTOMATION"),
                    severity=check.severity,
                    title=f"{check.component}: {check.code}",
                    description=(
                        f"{check.message}; actual={check.actual}, "
                        f"expected={check.expected}"
                    ),
                    source_phase={
                        "ORDER_LIFECYCLE": 2,
                        "PORTFOLIO": 4,
                        "CONTROL_PLANE": 5,
                        "SCHEDULER": 6,
                    }.get(check.component),
                    source_code=check.code,
                    recoverable=True,
                    recommended_action=actions.get(
                        check.code, "Review automation reports."
                    ),
                )
            )
        return tuple(incidents)

    def health_score(
        self,
        checks: Iterable[AutomationHealthCheck],
    ) -> float:
        penalties = {
            "CRITICAL": 25.0,
            "HIGH": 15.0,
            "MODERATE": 7.5,
            "LOW": 3.0,
        }
        score = 100.0
        for check in checks:
            if check.status == "FAIL":
                score -= penalties.get(check.severity, 5.0)
        return round(max(0.0, min(100.0, score)), 2)

    def overall_status(self, score: float) -> str:
        if score < self.policy.unhealthy_score_threshold:
            return "PHASE7_AUTOMATION_UNHEALTHY"
        if score < self.policy.degraded_score_threshold:
            return "PHASE7_AUTOMATION_DEGRADED"
        return "PHASE7_AUTOMATION_HEALTHY"

    def alert_summary(
        self,
        incidents: Iterable[AutomationIncident],
    ) -> dict[str, Any]:
        rows = tuple(incidents)
        by_severity = {
            severity: sum(row.severity == severity for row in rows)
            for severity in ("CRITICAL", "HIGH", "MODERATE", "LOW")
        }
        return {
            "incident_count": len(rows),
            "by_severity": by_severity,
            "requires_immediate_attention": (
                by_severity["CRITICAL"] > 0
            ),
            "highest_severity": next(
                (
                    severity
                    for severity in ("CRITICAL", "HIGH", "MODERATE", "LOW")
                    if by_severity[severity] > 0
                ),
                "NONE",
            ),
        }
