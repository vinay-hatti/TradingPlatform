from __future__ import annotations

from .policy import AutomatedPaperOrderHandoffPolicy
from .profile import (
    AutomatedPaperOrderCandidate,
    AutomatedPaperOrderHandoffAssessment,
)


class AutomatedPaperOrderHandoffEngine:
    def __init__(self, policy: AutomatedPaperOrderHandoffPolicy | None = None) -> None:
        self.policy = policy or AutomatedPaperOrderHandoffPolicy()
        self.policy.validate()

    @staticmethod
    def _grade(score: float) -> tuple[str, str]:
        if score >= 95:
            return "A", "LOW"
        if score >= 85:
            return "B", "MODERATE"
        if score >= 70:
            return "C", "SEVERE"
        return "F", "CRITICAL"

    def assess(
        self, candidate: AutomatedPaperOrderCandidate
    ) -> AutomatedPaperOrderHandoffAssessment:
        rejections: list[str] = []
        warnings: list[str] = []

        asset_class = candidate.asset_class.upper()
        side = candidate.side.upper()
        order_type = candidate.order_type.upper().replace(" ", "_")
        tif = candidate.time_in_force.upper()

        if candidate.portfolio_id != "PAPER-PRIMARY":
            warnings.append("NON_DEFAULT_PAPER_PORTFOLIO")
        if not candidate.candidate_id:
            rejections.append("CANDIDATE_ID_REQUIRED")
        if not candidate.symbol:
            rejections.append("SYMBOL_REQUIRED")
        if asset_class not in self.policy.allowed_asset_classes:
            rejections.append("ASSET_CLASS_NOT_ALLOWED")
        if side not in self.policy.allowed_sides:
            rejections.append("SIDE_NOT_ALLOWED")
        if candidate.quantity <= 0:
            rejections.append("QUANTITY_MUST_BE_POSITIVE")
        if candidate.quantity > self.policy.maximum_quantity:
            rejections.append("MAXIMUM_QUANTITY_EXCEEDED")
        if order_type not in self.policy.allowed_order_types:
            rejections.append("ORDER_TYPE_NOT_ALLOWED")
        if tif not in self.policy.allowed_time_in_force:
            rejections.append("TIME_IN_FORCE_NOT_ALLOWED")
        if self.policy.require_limit_orders_for_automated_entries and order_type != "LIMIT":
            rejections.append("AUTOMATED_ENTRY_REQUIRES_LIMIT_ORDER")
        if order_type in {"LIMIT", "STOP_LIMIT"} and (
            candidate.limit_price is None or candidate.limit_price <= 0
        ):
            rejections.append("VALID_LIMIT_PRICE_REQUIRED")
        if order_type in {"STOP", "STOP_LIMIT"} and (
            candidate.stop_price is None or candidate.stop_price <= 0
        ):
            rejections.append("VALID_STOP_PRICE_REQUIRED")
        if self.policy.require_institutional_approval and not candidate.institutional_allowed:
            rejections.append("INSTITUTIONAL_DECISION_REJECTED")
        if self.policy.require_risk_gateway_approval and not candidate.risk_gateway_allowed:
            rejections.append("RISK_GATEWAY_REJECTED")
        if candidate.decision_score < self.policy.minimum_decision_score:
            rejections.append("DECISION_SCORE_BELOW_MINIMUM")
        if candidate.probability < self.policy.minimum_probability:
            rejections.append("PROBABILITY_BELOW_MINIMUM")

        multiplier = 100.0 if asset_class == "OPTION" else 1.0
        reference_price = candidate.limit_price or 0.0
        estimated_notional = candidate.quantity * reference_price * multiplier
        if estimated_notional > self.policy.maximum_order_notional:
            rejections.append("MAXIMUM_ORDER_NOTIONAL_EXCEEDED")

        if asset_class == "OPTION":
            if candidate.quantity > self.policy.maximum_option_contracts:
                rejections.append("MAXIMUM_OPTION_CONTRACTS_EXCEEDED")
            if not candidate.expiry:
                rejections.append("OPTION_EXPIRY_REQUIRED")
            if candidate.strike is None or candidate.strike <= 0:
                rejections.append("OPTION_STRIKE_REQUIRED")
            if candidate.right.upper() not in {"C", "P", "CALL", "PUT"}:
                rejections.append("OPTION_RIGHT_REQUIRED")
            if candidate.multiplier and candidate.multiplier != "100":
                warnings.append("NON_STANDARD_OPTION_MULTIPLIER")

        checks = 16
        failed = len(set(rejections))
        score = max(0.0, 100.0 * (checks - min(checks, failed)) / checks)
        grade, severity = self._grade(score)
        allowed = not rejections
        return AutomatedPaperOrderHandoffAssessment(
            allowed=allowed,
            score=round(score, 2),
            grade=grade,
            severity=severity,
            recommendation="CREATE_CANONICAL_ORDER" if allowed else "REJECT",
            estimated_notional=round(estimated_notional, 6),
            warnings=tuple(dict.fromkeys(warnings)),
            rejection_reasons=tuple(dict.fromkeys(rejections)),
            metadata={
                "paper_only": True,
                "live_trading_enabled": False,
                "asset_class": asset_class,
                "normalized_order_type": order_type,
            },
        )
