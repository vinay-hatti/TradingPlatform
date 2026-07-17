from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .risk_gateway_service import RiskGatewayService


@dataclass(frozen=True)
class RiskGuardedWorkflowResult:
    valid: bool
    allowed: bool
    action: str
    aggregate_id: str
    recommendation: str
    risk_decision: Any = None
    workflow_result: Any = None
    rejection_reasons: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)


class OrderWorkflowRiskGuard:
    """Block broker submission unless the combined risk gateway approves."""

    def __init__(
        self,
        *,
        risk_gateway: RiskGatewayService,
        order_workflow_service,
    ) -> None:
        self.risk_gateway = risk_gateway
        self.order_workflow_service = order_workflow_service

    def submit(
        self,
        *,
        aggregate_id: str,
        route_id: str,
        instrument_mappings: dict[str, object],
        risk_evaluation_kwargs: dict[str, Any],
    ) -> RiskGuardedWorkflowResult:
        risk_decision = self.risk_gateway.evaluate(
            **risk_evaluation_kwargs
        )
        if not risk_decision.allowed:
            return RiskGuardedWorkflowResult(
                valid=True,
                allowed=False,
                action="SUBMIT",
                aggregate_id=aggregate_id,
                recommendation="BLOCK",
                risk_decision=risk_decision,
                rejection_reasons=risk_decision.rejection_reasons,
            )

        workflow_result = self.order_workflow_service.submit(
            aggregate_id,
            route_id=route_id,
            instrument_mappings=instrument_mappings,
        )
        return RiskGuardedWorkflowResult(
            valid=True,
            allowed=workflow_result.allowed,
            action="SUBMIT",
            aggregate_id=aggregate_id,
            recommendation=(
                "MONITOR" if workflow_result.allowed else "REJECT"
            ),
            risk_decision=risk_decision,
            workflow_result=workflow_result,
            rejection_reasons=workflow_result.rejection_reasons,
        )
