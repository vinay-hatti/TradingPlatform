from __future__ import annotations

from dataclasses import asdict, is_dataclass, replace
from typing import Any

from .trading_control_profile import CombinedRiskGatewayDecision


class RiskGatewayDecisionBridge:
    """Attach Phase 5 risk-gateway output to institutional decision results.

    The bridge is deliberately additive and provider-neutral. It supports
    dictionaries, mutable objects, and dataclasses whose schemas already
    contain the integration fields.
    """

    FIELD_MAP = {
        "risk_gateway_allowed": "allowed",
        "risk_gateway_score": "score",
        "risk_gateway_grade": "grade",
        "risk_gateway_severity": "severity",
        "risk_gateway_recommendation": "recommendation",
        "risk_gateway_rejection_reasons": "rejection_reasons",
        "risk_gateway_warnings": "warnings",
        "risk_gateway_evaluated_at": "evaluated_at",
    }

    @staticmethod
    def integration_payload(
        decision: CombinedRiskGatewayDecision,
    ) -> dict[str, Any]:
        payload = {
            target: getattr(decision, source)
            for target, source in RiskGatewayDecisionBridge.FIELD_MAP.items()
        }
        payload["risk_gateway_blocking_components"] = tuple(
            decision.metadata.get("blocking_components", ())
        )
        payload["risk_gateway_decision_count"] = int(
            decision.metadata.get("decision_count", 0)
        )
        payload["risk_gateway_details"] = asdict(decision)
        return payload

    def apply(
        self,
        institutional_result: Any,
        decision: CombinedRiskGatewayDecision,
    ) -> Any:
        payload = self.integration_payload(decision)

        if institutional_result is None:
            return payload

        if isinstance(institutional_result, dict):
            return {**institutional_result, **payload}

        if is_dataclass(institutional_result):
            dataclass_fields = getattr(
                institutional_result,
                "__dataclass_fields__",
                {},
            )
            accepted = {
                key: value
                for key, value in payload.items()
                if key in dataclass_fields
            }
            if accepted:
                return replace(institutional_result, **accepted)

            # Preserve the original dataclass and expose an integration envelope.
            return {
                "institutional_result": asdict(institutional_result),
                **payload,
            }

        for key, value in payload.items():
            try:
                setattr(institutional_result, key, value)
            except (AttributeError, TypeError):
                pass
        return institutional_result

    def decision_metadata(
        self,
        decision: CombinedRiskGatewayDecision,
    ) -> dict[str, Any]:
        return {
            "risk_gateway": self.integration_payload(decision),
            "execution_permitted": bool(decision.allowed),
            "execution_block_reason": (
                None
                if decision.allowed
                else ",".join(decision.rejection_reasons)
            ),
        }
