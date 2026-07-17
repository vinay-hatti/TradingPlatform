from __future__ import annotations
from typing import Any
from .options_greeks_engine import OptionsGreeksEngine
from .options_risk_policy import OptionsRiskPolicy
from .options_risk_profile import (
    OptionGreekProfile, OptionsRiskCheck, OptionsRiskDecision,
    ScenarioShockProfile,
)
from .options_scenario_engine import OptionsScenarioEngine
from .pretrade_risk_profile import PreTradeAccountProfile, PreTradeRiskRequest
from .strategy_margin_engine import StrategyMarginEngine

class OptionsRiskEngine:
    def __init__(self, policy: OptionsRiskPolicy | None = None) -> None:
        self.policy = policy or OptionsRiskPolicy()
        self.policy.validate()
        self.greeks_engine = OptionsGreeksEngine(self.policy)
        self.scenario_engine = OptionsScenarioEngine(self.policy)
        self.margin_engine = StrategyMarginEngine(self.policy)

    @staticmethod
    def _grade(score: float) -> tuple[str, str]:
        if score >= 95: return "A", "LOW"
        if score >= 85: return "B", "MODERATE"
        if score >= 70: return "C", "SEVERE"
        return "F", "CRITICAL"

    def evaluate(
        self,
        order: PreTradeRiskRequest,
        account: PreTradeAccountProfile | None,
        greek_legs: tuple[OptionGreekProfile, ...],
        scenarios: tuple[ScenarioShockProfile, ...] | None = None,
    ) -> OptionsRiskDecision:
        checks = []

        def add(name: str, passed: bool, message: str, *, required: bool = True, metadata: dict[str, Any] | None = None) -> None:
            checks.append(OptionsRiskCheck(
                name=name,
                passed=bool(passed),
                required=required,
                score=100.0 if passed else 0.0,
                severity="LOW" if passed else "CRITICAL",
                message=message,
                metadata=metadata or {},
            ))

        add("option_legs_present", bool(greek_legs), "Option Greek profiles are available.")
        order_option_leg_ids = {
            leg.leg_id for leg in order.legs
            if leg.asset_class.upper() == "OPTION"
        }
        greek_leg_ids = {leg.leg_id for leg in greek_legs}
        add(
            "greek_leg_coverage",
            order_option_leg_ids.issubset(greek_leg_ids),
            "All option order legs have Greek profiles.",
            required=self.policy.reject_missing_greeks,
        )

        for leg in greek_legs:
            add(
                f"underlying_price:{leg.leg_id}",
                (
                    leg.underlying_price is not None
                    and leg.underlying_price > 0
                ),
                "Underlying price must be available and positive.",
                required=(
                    self.policy.reject_missing_underlying_price
                    or self.policy.reject_non_positive_underlying_price
                ),
            )

        greeks = self.greeks_engine.aggregate(greek_legs)
        scenario_results = self.scenario_engine.evaluate(
            greek_legs,
            scenarios,
        )
        worst = max(
            scenario_results,
            key=lambda item: item.loss,
            default=None,
        )
        margin = self.margin_engine.evaluate(greek_legs, account)

        add("absolute_delta", abs(greeks.delta) <= self.policy.maximum_absolute_delta, "Absolute delta is within policy.")
        add("absolute_gamma", abs(greeks.gamma) <= self.policy.maximum_absolute_gamma, "Absolute gamma is within policy.")
        add("absolute_vega", abs(greeks.vega) <= self.policy.maximum_absolute_vega, "Absolute vega is within policy.")
        add("absolute_theta", abs(greeks.theta) <= self.policy.maximum_absolute_theta, "Absolute theta is within policy.")
        add("absolute_rho", abs(greeks.rho) <= self.policy.maximum_absolute_rho, "Absolute rho is within policy.")

        worst_loss = worst.loss if worst is not None else 0.0
        add(
            "maximum_scenario_loss",
            worst_loss <= self.policy.maximum_scenario_loss,
            "Worst scenario loss is within absolute limit.",
            metadata={"loss": worst_loss, "limit": self.policy.maximum_scenario_loss},
        )
        nlv = account.net_liquidation if account is not None else 0.0
        loss_pct = worst_loss / nlv if nlv > 0 else None
        add(
            "scenario_loss_pct_net_liquidation",
            loss_pct is not None
            and loss_pct <= self.policy.maximum_scenario_loss_pct_of_net_liquidation,
            "Worst scenario loss percentage is within policy.",
        )
        add(
            "defined_risk",
            margin.defined_risk
            or not self.policy.require_defined_risk_for_multi_leg_options,
            "Strategy satisfies defined-risk requirements.",
            required=self.policy.require_defined_risk_for_multi_leg_options,
        )
        add(
            "uncovered_short_option",
            not margin.uncovered_short_option
            or not self.policy.reject_uncovered_short_options,
            "Uncovered short options are rejected when configured.",
            required=self.policy.reject_uncovered_short_options,
        )
        add(
            "maximum_strategy_margin",
            margin.margin_required <= self.policy.maximum_strategy_margin,
            "Strategy margin is within absolute limit.",
        )
        add(
            "margin_utilization",
            margin.margin_utilization is not None
            and margin.margin_utilization <= self.policy.maximum_margin_utilization,
            "Strategy margin utilization is within policy.",
        )

        required_checks = [check for check in checks if check.required]
        failed = [check for check in required_checks if not check.passed]
        score = (
            sum(check.score for check in required_checks) / len(required_checks)
            if required_checks else 100.0
        )
        allowed = not failed and score >= self.policy.minimum_approval_score
        if not self.policy.fail_closed:
            allowed = score >= self.policy.minimum_approval_score
        grade, severity = self._grade(score)

        return OptionsRiskDecision(
            valid=True,
            allowed=allowed,
            aggregate_id=order.aggregate_id,
            client_order_id=order.client_order_id,
            account_id=order.account_id,
            score=round(score, 2),
            grade=grade,
            severity=severity,
            recommendation="APPROVE" if allowed else "REJECT",
            greeks=greeks,
            scenarios=scenario_results,
            worst_scenario=worst,
            margin=margin,
            account=account,
            order=order,
            checks=tuple(checks),
            rejection_reasons=tuple(check.name.upper() for check in failed),
            metadata={
                "worst_scenario_loss": worst_loss,
                "worst_scenario_loss_pct_of_net_liquidation": loss_pct,
                "strategy_classification": margin.strategy_classification,
            },
        )
