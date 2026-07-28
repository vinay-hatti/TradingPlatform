from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
from typing import Any, Mapping

from .engine import AutomationControlPlaneEngine, stable_cycle_id
from .policy import AutomationControlPlanePolicy
from .profile import AutomatedTradingCycleResult


class AutomationControlPlaneService:
    def __init__(
        self,
        policy: AutomationControlPlanePolicy | None = None,
    ) -> None:
        self.policy = policy or AutomationControlPlanePolicy()
        self.policy.validate()
        self.engine = AutomationControlPlaneEngine(self.policy)

    def execute(
        self,
        portfolio_id: str,
        reports: Mapping[int, Mapping[str, Any] | None],
        *,
        mode: str = "DRY_RUN",
        confirmation: str = "",
        started_at: str | None = None,
    ) -> AutomatedTradingCycleResult:
        start = started_at or datetime.now(timezone.utc).isoformat()
        cycle_id = stable_cycle_id(portfolio_id, start)
        phases = self.engine.validate_dependencies(reports)
        phase4 = reports.get(4)
        decision = self.engine.authorize(
            portfolio_id,
            mode,
            confirmation=confirmation,
            phase4_report=phase4,
        )
        summary = self.engine.consolidated_summary(reports)
        audit = self.engine.audit_events(cycle_id, decision, phases)

        errors: list[str] = []
        warnings: list[str] = []
        for phase in phases:
            warnings.extend(phase.warnings)
            errors.extend(phase.errors)
            if phase.status == "MISSING_REQUIRED":
                errors.append(f"PHASE_{phase.phase}_REQUIRED_REPORT_MISSING")
            elif phase.status in {"FAILED", "DEGRADED"}:
                warnings.append(f"PHASE_{phase.phase}_{phase.status}")

        if not decision.allowed:
            errors.extend(decision.reason_codes)

        if errors:
            status = "PHASE5_AUTOMATION_BLOCKED"
        elif warnings:
            status = "PHASE5_AUTOMATION_READY_WITH_WARNINGS"
        else:
            status = "PHASE5_AUTOMATION_READY"

        if mode.upper() == "SUBMIT" and decision.allowed and not errors:
            status = "PHASE5_AUTOMATED_PAPER_CYCLE_AUTHORIZED"

        end = datetime.now(timezone.utc).isoformat()
        duration = max(
            0.0,
            (
                datetime.fromisoformat(end)
                - datetime.fromisoformat(start)
            ).total_seconds(),
        )
        return AutomatedTradingCycleResult(
            milestone=51,
            phase=5,
            cycle_id=cycle_id,
            portfolio_id=portfolio_id,
            mode=mode.upper(),
            status=status,
            control_decision=asdict(decision),
            phases=tuple(asdict(row) for row in phases),
            consolidated_summary=summary,
            audit_events=audit,
            started_at=start,
            completed_at=end,
            duration_seconds=round(duration, 6),
            warnings=tuple(dict.fromkeys(warnings)),
            errors=tuple(dict.fromkeys(errors)),
            metadata={
                "environment": "PAPER",
                "live_trading_enabled": False,
                "kill_switch_active": self.policy.kill_switch_active,
                "paper_routing_enabled": self.policy.paper_routing_enabled,
                "execution_note": (
                    "Phase 5 authorizes and audits the cycle. "
                    "Existing phase CLIs remain the execution surfaces."
                ),
            },
        )
