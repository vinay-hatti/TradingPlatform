from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Any, Mapping

from .engine import OperationalReadinessEngine
from .policy import OperationalReadinessPolicy
from .profile import OperationalReadinessResult
from .validators import (
    DependencyValidator,
    EnvironmentValidator,
    GovernanceValidator,
)


class OperationalReadinessService:
    def __init__(
        self,
        policy: OperationalReadinessPolicy | None = None,
    ) -> None:
        self.policy = policy or OperationalReadinessPolicy()
        self.policy.validate()
        self.engine = OperationalReadinessEngine(self.policy)

    def execute(
        self,
        portfolio_id: str,
        phase_reports: Mapping[int, Mapping[str, Any]],
        *,
        repo_root: str | Path,
        mode: str = "FULL",
        require_database_url: bool = False,
        require_polygon_key: bool = False,
        broker_mode: str = "PAPER",
    ) -> OperationalReadinessResult:
        normalized_mode = mode.upper()
        controls = []

        if normalized_mode in {"VALIDATE", "READINESS", "FULL"}:
            controls.extend(
                EnvironmentValidator().validate(
                    repo_root=repo_root,
                    require_database_url=require_database_url,
                    require_polygon_key=require_polygon_key,
                    broker_mode=broker_mode,
                )
            )

        if normalized_mode in {"ACCEPTANCE_TEST", "READINESS", "FULL"}:
            controls.extend(
                DependencyValidator().validate(
                    phase_reports,
                    self.policy.require_phase_reports,
                )
            )
            controls.extend(
                GovernanceValidator().validate(phase_reports)
            )

        categories = self.engine.category_scores(controls)
        score = self.engine.overall_score(controls)
        status, recommendation = self.engine.final_status(
            controls, categories, score
        )
        summary = self.engine.acceptance_summary(controls)

        warnings = tuple(
            warning for row in controls for warning in row.warnings
        )
        errors = tuple(error for row in controls for error in row.errors)
        sign_off = {
            "eligible": status == "PHASE9_OPERATIONALLY_READY",
            "conditional": status == "PHASE9_READY_WITH_CONDITIONS",
            "signed": False,
            "signed_by": "",
            "signed_at": "",
            "statement": (
                "Milestone 51 paper-trading automation has completed "
                "operational readiness evaluation."
            ),
        }
        return OperationalReadinessResult(
            milestone=51,
            phase=9,
            portfolio_id=portfolio_id,
            mode=normalized_mode,
            overall_status=status,
            recommendation=recommendation,
            overall_score=score,
            category_scores=tuple(asdict(row) for row in categories),
            controls=tuple(asdict(row) for row in controls),
            acceptance_summary=summary,
            sign_off=sign_off,
            warnings=tuple(dict.fromkeys(warnings)),
            errors=tuple(dict.fromkeys(errors)),
            metadata={
                "environment": "PAPER",
                "live_trading_enabled": False,
                "required_phases": list(self.policy.require_phase_reports),
                "milestone_complete": (
                    status in {
                        "PHASE9_OPERATIONALLY_READY",
                        "PHASE9_READY_WITH_CONDITIONS",
                    }
                ),
            },
        )
