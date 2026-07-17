from __future__ import annotations

from typing import Any

from .pretrade_risk_classifier import classify_option_risk
from .pretrade_risk_policy import PreTradeRiskPolicy
from .pretrade_risk_profile import (
    PreTradeAccountProfile,
    PreTradeExposureProfile,
    PreTradeRiskCheck,
    PreTradeRiskDecision,
    PreTradeRiskRequest,
)


def _direction(side: str) -> float:
    return -1.0 if side.upper().startswith("SELL") else 1.0


class PreTradeRiskEngine:
    def __init__(self, policy: PreTradeRiskPolicy | None = None) -> None:
        self.policy = policy or PreTradeRiskPolicy()
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

    def calculate_exposure(
        self,
        request: PreTradeRiskRequest,
        account: PreTradeAccountProfile | None,
    ) -> PreTradeExposureProfile:
        gross_notional = 0.0
        net_notional = 0.0
        gross_premium = 0.0
        net_premium = 0.0
        contracts = 0
        equity_quantity = 0.0

        for leg in request.legs:
            price = float(leg.price or 0.0)
            multiplier = max(int(leg.multiplier or 1), 1)
            leg_value = abs(leg.quantity) * price * multiplier
            direction = _direction(leg.side)

            gross_notional += leg_value
            net_notional += direction * leg_value

            if leg.asset_class.upper() == "OPTION":
                contracts += int(abs(leg.quantity))
                gross_premium += leg_value
                net_premium += direction * leg_value
            elif leg.asset_class.upper() == "EQUITY":
                equity_quantity += abs(leg.quantity)

        defined_risk, classification = classify_option_risk(request)

        if defined_risk:
            maximum_loss = gross_premium if gross_premium > 0 else gross_notional
            buying_power_required = max(abs(net_premium), maximum_loss)
        else:
            maximum_loss = None
            buying_power_required = gross_notional

        maximum_profit = None
        order_pct_bp = (
            buying_power_required / account.buying_power
            if account is not None and account.buying_power > 0
            else None
        )
        order_pct_nlv = (
            buying_power_required / account.net_liquidation
            if account is not None and account.net_liquidation > 0
            else None
        )

        return PreTradeExposureProfile(
            gross_notional=round(gross_notional, 6),
            net_notional=round(net_notional, 6),
            gross_premium=round(gross_premium, 6),
            net_premium=round(net_premium, 6),
            maximum_loss=(
                round(maximum_loss, 6)
                if maximum_loss is not None
                else None
            ),
            maximum_profit=maximum_profit,
            total_contracts=contracts,
            total_equity_quantity=round(equity_quantity, 6),
            defined_risk=defined_risk,
            risk_classification=classification,
            buying_power_required=round(buying_power_required, 6),
            order_pct_of_buying_power=order_pct_bp,
            order_pct_of_net_liquidation=order_pct_nlv,
        )

    def evaluate(
        self,
        request: PreTradeRiskRequest,
        account: PreTradeAccountProfile | None,
    ) -> PreTradeRiskDecision:
        checks: list[PreTradeRiskCheck] = []
        warnings: list[str] = []

        def add(
            name: str,
            passed: bool,
            message: str,
            *,
            required: bool = True,
            metadata: dict[str, Any] | None = None,
        ) -> None:
            checks.append(
                PreTradeRiskCheck(
                    name=name,
                    passed=bool(passed),
                    required=required,
                    score=100.0 if passed else 0.0,
                    severity="LOW" if passed else "CRITICAL",
                    message=message,
                    metadata=metadata or {},
                )
            )

        add(
            "account_profile",
            account is not None or not self.policy.reject_missing_account_profile,
            "Account profile is available.",
            required=self.policy.reject_missing_account_profile,
        )

        exposure = self.calculate_exposure(request, account)

        add("legs_present", bool(request.legs), "Order contains at least one leg.")

        for leg in request.legs:
            add(
                f"quantity:{leg.leg_id}",
                leg.quantity > 0 or not self.policy.reject_zero_or_negative_quantity,
                "Leg quantity must be positive.",
            )
            add(
                f"price:{leg.leg_id}",
                (
                    leg.price is not None
                    and leg.price > 0
                )
                or (
                    request.order_type.upper() == "MARKET"
                    and self.policy.allow_market_orders_without_limit_price
                )
                or not self.policy.reject_missing_market_price,
                "Leg market or reference price must be positive.",
            )

        add(
            "maximum_order_notional",
            exposure.gross_notional <= self.policy.maximum_order_notional,
            "Gross order notional is within policy.",
            metadata={
                "gross_notional": exposure.gross_notional,
                "limit": self.policy.maximum_order_notional,
            },
        )
        add(
            "maximum_order_premium",
            exposure.gross_premium <= self.policy.maximum_order_premium,
            "Gross option premium is within policy.",
            metadata={
                "gross_premium": exposure.gross_premium,
                "limit": self.policy.maximum_order_premium,
            },
        )
        add(
            "maximum_contracts",
            exposure.total_contracts <= self.policy.maximum_contracts_per_order,
            "Option contract count is within policy.",
        )
        add(
            "maximum_equity_quantity",
            exposure.total_equity_quantity <= self.policy.maximum_equity_quantity,
            "Equity quantity is within policy.",
        )
        add(
            "defined_risk",
            exposure.defined_risk
            or not self.policy.require_defined_risk_for_multi_leg_options,
            "Order satisfies defined-risk requirements.",
            required=self.policy.require_defined_risk_for_multi_leg_options,
        )
        add(
            "undefined_risk",
            exposure.defined_risk
            or not self.policy.reject_undefined_risk_option_orders,
            "Undefined-risk option orders are rejected when configured.",
            required=self.policy.reject_undefined_risk_option_orders,
        )

        if account is not None:
            add(
                "positive_buying_power",
                account.buying_power > self.policy.minimum_available_buying_power
                or not self.policy.require_positive_buying_power,
                "Account buying power is positive.",
            )
            add(
                "positive_net_liquidation",
                account.net_liquidation > 0
                or not self.policy.require_positive_net_liquidation,
                "Account net liquidation is positive.",
            )
            add(
                "buying_power_available",
                exposure.buying_power_required <= account.buying_power,
                "Required buying power is available.",
                metadata={
                    "required": exposure.buying_power_required,
                    "available": account.buying_power,
                },
            )
            add(
                "buying_power_concentration",
                (
                    exposure.order_pct_of_buying_power is not None
                    and exposure.order_pct_of_buying_power
                    <= self.policy.maximum_order_pct_of_buying_power
                ),
                "Order percentage of buying power is within policy.",
            )
            add(
                "net_liquidation_concentration",
                (
                    exposure.order_pct_of_net_liquidation is not None
                    and exposure.order_pct_of_net_liquidation
                    <= self.policy.maximum_order_pct_of_net_liquidation
                ),
                "Order percentage of net liquidation is within policy.",
            )

        required_checks = [check for check in checks if check.required]
        failed = [check for check in required_checks if not check.passed]
        score = (
            sum(check.score for check in required_checks)
            / len(required_checks)
            if required_checks else 100.0
        )
        allowed = (
            not failed
            and score >= self.policy.minimum_approval_score
        )
        if not self.policy.fail_closed:
            allowed = score >= self.policy.minimum_approval_score

        grade, severity = self._grade(score)
        return PreTradeRiskDecision(
            valid=True,
            allowed=allowed,
            aggregate_id=request.aggregate_id,
            client_order_id=request.client_order_id,
            account_id=request.account_id,
            score=round(score, 2),
            grade=grade,
            severity=severity,
            recommendation="APPROVE" if allowed else "REJECT",
            exposure=exposure,
            account=account,
            checks=tuple(checks),
            warnings=tuple(warnings),
            rejection_reasons=tuple(
                check.name.upper() for check in failed
            ),
            metadata={
                "risk_classification": exposure.risk_classification,
            },
        )
