from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timezone
from .deployment_adapter import DeploymentAdapter
from .rollback_policy import RollbackPlan

@dataclass(frozen=True)
class RollbackExecutionResult:
    deployment_id: str
    success: bool
    restored_version: str
    restored_slot: str
    reason: str
    completed_at: str

class RollbackExecutionService:
    def __init__(self, adapter: DeploymentAdapter) -> None:
        self.adapter = adapter

    def execute(self, *, environment: str, plan: RollbackPlan, restore_slot: str) -> RollbackExecutionResult:
        valid, errors = plan.validate()
        if not valid:
            return RollbackExecutionResult(
                deployment_id=plan.deployment_id, success=False,
                restored_version=plan.target_artifact_version,
                restored_slot=restore_slot, reason=",".join(errors),
                completed_at=datetime.now(timezone.utc).isoformat(),
            )
        self.adapter.set_traffic(environment=environment, slot=restore_slot, percent=100)
        self.adapter.promote_slot(environment=environment, slot=restore_slot)
        if plan.restart_services:
            self.adapter.restart(environment=environment, slot=restore_slot)
        return RollbackExecutionResult(
            deployment_id=plan.deployment_id, success=True,
            restored_version=plan.target_artifact_version,
            restored_slot=restore_slot, reason="ROLLBACK_COMPLETED",
            completed_at=datetime.now(timezone.utc).isoformat(),
        )
