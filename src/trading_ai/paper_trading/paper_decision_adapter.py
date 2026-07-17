from __future__ import annotations
from typing import Any
from .paper_scan_profile import PaperDecisionPipelineResult, PaperScanCandidate

class PaperDecisionPipelineAdapter:
    """Normalize institutional-decision and risk-gateway results."""

    @staticmethod
    def _value(obj: Any, name: str, default=None):
        if obj is None:
            return default
        if isinstance(obj, dict):
            return obj.get(name, default)
        return getattr(obj, name, default)

    def combine(
        self,
        candidate: PaperScanCandidate,
        *,
        institutional_decision: Any,
        risk_gateway_decision: Any,
        require_decision_approval: bool = True,
        require_risk_gateway_approval: bool = True,
    ) -> PaperDecisionPipelineResult:
        institutional_allowed = bool(
            self._value(
                institutional_decision,
                "allowed",
                self._value(institutional_decision, "approved", False),
            )
        )
        risk_allowed = bool(
            self._value(risk_gateway_decision, "allowed", False)
        )

        rejection_reasons = []
        warnings = []
        if require_decision_approval and not institutional_allowed:
            rejection_reasons.append("INSTITUTIONAL_DECISION_REJECTED")
        if require_risk_gateway_approval and not risk_allowed:
            rejection_reasons.append("RISK_GATEWAY_REJECTED")

        rejection_reasons.extend(
            self._value(institutional_decision, "rejection_reasons", ()) or ()
        )
        rejection_reasons.extend(
            self._value(risk_gateway_decision, "rejection_reasons", ()) or ()
        )
        warnings.extend(
            self._value(institutional_decision, "warnings", ()) or ()
        )
        warnings.extend(
            self._value(risk_gateway_decision, "warnings", ()) or ()
        )

        approved = not rejection_reasons
        return PaperDecisionPipelineResult(
            candidate_id=candidate.candidate_id,
            symbol=candidate.symbol,
            strategy_name=candidate.strategy_name,
            approved=approved,
            score=candidate.score,
            probability=candidate.probability,
            recommendation="CREATE_ORDER" if approved else "REJECT",
            institutional_decision=institutional_decision,
            risk_gateway_decision=risk_gateway_decision,
            rejection_reasons=tuple(dict.fromkeys(map(str, rejection_reasons))),
            warnings=tuple(dict.fromkeys(map(str, warnings))),
        )
