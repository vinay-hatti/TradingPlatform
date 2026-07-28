from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any, Iterable, Mapping

from .policy import AutomationControlPlanePolicy
from .profile import AutomationControlDecision, AutomationPhaseStatus


def stable_cycle_id(portfolio_id: str, started_at: str) -> str:
    digest = hashlib.sha256(
        f"{portfolio_id}|{started_at}".encode()
    ).hexdigest()[:24]
    return f"M51-CYCLE-{digest.upper()}"


class AutomationControlPlaneEngine:
    def __init__(
        self,
        policy: AutomationControlPlanePolicy | None = None,
    ) -> None:
        self.policy = policy or AutomationControlPlanePolicy()
        self.policy.validate()

    def authorize(
        self,
        portfolio_id: str,
        mode: str,
        *,
        confirmation: str = "",
        phase4_report: Mapping[str, Any] | None = None,
    ) -> AutomationControlDecision:
        normalized = mode.upper()
        if normalized not in {"DRY_RUN", "SUBMIT", "MONITOR_ONLY"}:
            raise ValueError("mode must be DRY_RUN, SUBMIT, or MONITOR_ONLY")

        reasons: list[str] = []
        required_confirmation = ""
        health = None
        risk_breaches = 0
        if phase4_report:
            health = float(
                (phase4_report.get("health") or {}).get("overall", 0.0)
            )
            risk_breaches = len(phase4_report.get("risk_breaches") or ())

        if self.policy.live_trading_enabled:
            reasons.append("LIVE_TRADING_ENABLED")
        if normalized == "SUBMIT" and not self.policy.paper_routing_enabled:
            reasons.append("PAPER_ROUTING_DISABLED")
        if self.policy.kill_switch_active and normalized == "SUBMIT":
            reasons.append("KILL_SWITCH_ACTIVE")
        if (
            normalized == "SUBMIT"
            and self.policy.block_new_entries_on_low_health
            and health is not None
            and health < self.policy.minimum_portfolio_health_score
        ):
            reasons.append("PORTFOLIO_HEALTH_BELOW_MINIMUM")
        if (
            normalized == "SUBMIT"
            and self.policy.block_new_entries_on_risk_breach
            and risk_breaches > 0
        ):
            reasons.append("PORTFOLIO_RISK_BREACH_ACTIVE")

        if normalized == "SUBMIT":
            required_confirmation = (
                self.policy.submit_confirmation_template.format(
                    portfolio_id=portfolio_id
                )
            )
            if confirmation != required_confirmation:
                reasons.append("CONFIRMATION_MISMATCH")

        return AutomationControlDecision(
            allowed=not reasons,
            mode=normalized,
            reason_codes=tuple(dict.fromkeys(reasons)),
            kill_switch_active=self.policy.kill_switch_active,
            paper_routing_enabled=self.policy.paper_routing_enabled,
            live_trading_enabled=self.policy.live_trading_enabled,
            required_confirmation=required_confirmation,
            metadata={
                "portfolio_health_score": health,
                "risk_breach_count": risk_breaches,
                "environment": self.policy.environment,
            },
        )

    def validate_dependencies(
        self,
        reports: Mapping[int, Mapping[str, Any] | None],
    ) -> tuple[AutomationPhaseStatus, ...]:
        requirements = {
            1: self.policy.require_phase1,
            2: self.policy.require_phase2,
            3: self.policy.require_phase3,
            4: self.policy.require_phase4,
        }
        names = {
            1: "INSTITUTIONAL_ORDER_HANDOFF",
            2: "ORDER_LIFECYCLE",
            3: "POSITION_MANAGEMENT",
            4: "PORTFOLIO_MANAGEMENT",
        }
        statuses: list[AutomationPhaseStatus] = []
        for phase in range(1, 5):
            payload = reports.get(phase)
            required = requirements[phase]
            if payload is None:
                status = "MISSING_REQUIRED" if required else "NOT_PROVIDED"
                warnings = () if required else ("OPTIONAL_PHASE_NOT_PROVIDED",)
                errors = ("REQUIRED_PHASE_REPORT_MISSING",) if required else ()
            else:
                source_status = str(payload.get("status") or "UNKNOWN")
                error_rows = tuple(payload.get("errors") or ())
                status = "READY" if not error_rows else "FAILED"
                warnings = tuple(payload.get("warnings") or ())
                errors = error_rows
                if source_status in {
                    "UNKNOWN",
                    "FAILED",
                    "ERROR",
                    "PHASE1_NO_ORDERS_CREATED",
                }:
                    status = "DEGRADED" if not errors else "FAILED"
            statuses.append(
                AutomationPhaseStatus(
                    phase=phase,
                    name=names[phase],
                    required=required,
                    status=status,
                    warnings=warnings,
                    errors=errors,
                    metadata={
                        "source_status": (
                            None if payload is None else payload.get("status")
                        )
                    },
                )
            )
        return tuple(statuses)

    def consolidated_summary(
        self,
        reports: Mapping[int, Mapping[str, Any] | None],
    ) -> dict[str, Any]:
        phase1 = reports.get(1) or {}
        phase2 = reports.get(2) or {}
        phase3 = reports.get(3) or {}
        phase4 = reports.get(4) or {}
        return {
            "phase1": {
                "handoff_succeeded": int(
                    phase1.get("handoff_succeeded", 0) or 0
                ),
                "handoff_rejected": int(
                    phase1.get("handoff_rejected", 0) or 0
                ),
            },
            "phase2": {
                "active_orders": int(
                    (phase2.get("summary") or {}).get("active_orders", 0) or 0
                ),
                "terminal_orders": int(
                    (phase2.get("summary") or {}).get("terminal_orders", 0) or 0
                ),
                "execution_count": int(
                    (phase2.get("summary") or {}).get("execution_count", 0) or 0
                ),
                "stale_orders": int(
                    (phase2.get("summary") or {}).get("stale_orders", 0) or 0
                ),
            },
            "phase3": {
                "total_positions": int(
                    phase3.get("total_positions", 0) or 0
                ),
                "exit_candidates": int(
                    phase3.get("exit_candidates", 0) or 0
                ),
                "submitted_exits": int(
                    phase3.get("submitted_exits", 0) or 0
                ),
            },
            "phase4": {
                "health_score": float(
                    (phase4.get("health") or {}).get("overall", 0.0) or 0.0
                ),
                "health_grade": str(
                    (phase4.get("health") or {}).get("grade", "UNKNOWN")
                ),
                "risk_breach_count": len(
                    phase4.get("risk_breaches") or ()
                ),
                "recommendation_count": len(
                    phase4.get("recommendations") or ()
                ),
                "net_liquidation_value": float(
                    (phase4.get("state") or {}).get(
                        "net_liquidation_value", 0.0
                    ) or 0.0
                ),
                "daily_pnl": float(
                    (phase4.get("state") or {}).get("daily_pnl", 0.0) or 0.0
                ),
            },
        }

    def audit_events(
        self,
        cycle_id: str,
        decision: AutomationControlDecision,
        phases: Iterable[AutomationPhaseStatus],
    ) -> tuple[dict[str, Any], ...]:
        now = datetime.now(timezone.utc).isoformat()
        events: list[dict[str, Any]] = [
            {
                "event_id": f"{cycle_id}-CONTROL",
                "event_type": "CONTROL_DECISION",
                "occurred_at": now,
                "allowed": decision.allowed,
                "mode": decision.mode,
                "reason_codes": list(decision.reason_codes),
            }
        ]
        for phase in phases:
            events.append(
                {
                    "event_id": f"{cycle_id}-PHASE-{phase.phase}",
                    "event_type": "PHASE_DEPENDENCY",
                    "occurred_at": now,
                    "phase": phase.phase,
                    "name": phase.name,
                    "status": phase.status,
                    "warnings": list(phase.warnings),
                    "errors": list(phase.errors),
                }
            )
        return tuple(events)
