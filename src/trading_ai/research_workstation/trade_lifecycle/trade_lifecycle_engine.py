from __future__ import annotations

from datetime import date
from typing import Any, Mapping

from .trade_lifecycle_policy import TradeLifecyclePolicy
from .trade_lifecycle_profile import (
    AdjustmentActionProfile,
    EntryPlanProfile,
    ExitPlanProfile,
    LifecycleCheckpointProfile,
    TradeLifecycleProfile,
)


class TradeLifecycleEngine:
    def __init__(
        self,
        policy: TradeLifecyclePolicy | None = None,
    ) -> None:
        self.policy = policy or TradeLifecyclePolicy()
        self.policy.validate()

    @staticmethod
    def _get(source: Any, name: str, default: Any = None) -> Any:
        if isinstance(source, Mapping):
            return source.get(name, default)
        return getattr(source, name, default)

    @staticmethod
    def _grade(score: float) -> str:
        if score >= 90:
            return "A"
        if score >= 80:
            return "B"
        if score >= 70:
            return "C"
        if score >= 60:
            return "D"
        return "F"

    @staticmethod
    def _severity(rejections: int, warnings: int) -> str:
        if rejections >= 2:
            return "CRITICAL"
        if rejections == 1:
            return "HIGH"
        if warnings >= 3:
            return "MODERATE"
        if warnings:
            return "LOW"
        return "NONE"

    def plan(
        self,
        *,
        symbol: str,
        strategy_name: str,
        expiration: date,
        as_of_date: date,
        entry_limit_price: float,
        net_credit_debit: float,
        maximum_profit: float | None,
        maximum_loss: float | None,
        probability_of_profit: float,
        confidence: float,
        spread_pct: float,
        defined_risk: bool,
        current_delta_exposure: float = 0.0,
        event_date: date | None = None,
    ) -> TradeLifecycleProfile:
        if expiration < as_of_date:
            raise ValueError("Expiration cannot be before as-of date.")
        if entry_limit_price < 0:
            raise ValueError("Entry limit price cannot be negative.")

        dte = (expiration - as_of_date).days
        reasons: list[str] = []
        blockers: list[str] = []
        warnings: list[str] = []
        rejections: list[str] = []

        if dte < self.policy.minimum_days_to_expiration:
            blockers.append("Days to expiration below minimum policy.")
        elif not (
            self.policy.preferred_entry_dte_min
            <= dte
            <= self.policy.preferred_entry_dte_max
        ):
            reasons.append("Entry DTE is outside the preferred window.")
            warnings.append("Entry timing is outside preferred DTE.")

        if confidence < self.policy.minimum_entry_confidence:
            blockers.append("Entry confidence below policy threshold.")
        if probability_of_profit < self.policy.minimum_entry_confidence:
            warnings.append("Probability of profit is below target.")
        if spread_pct > self.policy.maximum_entry_spread_pct:
            blockers.append("Bid/ask spread exceeds entry policy.")
        if self.policy.require_defined_risk and not defined_risk:
            blockers.append("Defined-risk structure is required.")

        if blockers:
            rejections.extend(blockers)

        entry_allowed = not blockers
        entry_status = (
            "READY"
            if entry_allowed and not warnings
            else "READY_WITH_WARNINGS"
            if entry_allowed
            else "BLOCKED"
        )

        if net_credit_debit >= 0:
            minimum_credit_or_maximum_debit = round(
                entry_limit_price * 0.98, 6
            )
            maximum_acceptable_price = round(
                entry_limit_price, 6
            )
        else:
            minimum_credit_or_maximum_debit = round(
                entry_limit_price * 1.02, 6
            )
            maximum_acceptable_price = round(
                entry_limit_price * 1.02, 6
            )

        entry = EntryPlanProfile(
            entry_status=entry_status,
            entry_allowed=entry_allowed,
            entry_window=(
                "PREFERRED"
                if self.policy.preferred_entry_dte_min
                <= dte
                <= self.policy.preferred_entry_dte_max
                else "NON_PREFERRED"
            ),
            order_type="LIMIT",
            time_in_force="DAY",
            target_limit_price=round(entry_limit_price, 6),
            maximum_acceptable_price=maximum_acceptable_price,
            minimum_credit_or_maximum_debit=(
                minimum_credit_or_maximum_debit
            ),
            confidence=round(confidence, 6),
            days_to_expiration=dte,
            rationale=tuple(reasons),
            blockers=tuple(blockers),
        )

        max_profit_value = (
            float(maximum_profit)
            if maximum_profit is not None
            else 0.0
        )
        max_loss_value = (
            float(maximum_loss)
            if maximum_loss is not None
            else 0.0
        )
        profit_target = (
            max_profit_value
            * self.policy.profit_target_pct_of_max_profit
        )
        credit_value = max(0.0, net_credit_debit)
        stop_loss_from_credit = (
            credit_value * self.policy.stop_loss_multiple_of_credit
        )
        stop_loss_from_max_loss = (
            max_loss_value * self.policy.maximum_loss_pct
        )
        stop_loss = (
            min(
                value
                for value in (
                    stop_loss_from_credit,
                    stop_loss_from_max_loss,
                )
                if value > 0
            )
            if any(
                value > 0
                for value in (
                    stop_loss_from_credit,
                    stop_loss_from_max_loss,
                )
            )
            else 0.0
        )

        event_risk_exit_required = False
        if event_date is not None:
            days_to_event = (event_date - as_of_date).days
            event_risk_exit_required = (
                0 <= days_to_event <= self.policy.event_risk_exit_days
            )
            if event_risk_exit_required:
                warnings.append("Imminent event risk requires exit review.")

        exit_plan = ExitPlanProfile(
            profit_target_value=round(profit_target, 6),
            profit_target_pct=(
                self.policy.profit_target_pct_of_max_profit
            ),
            stop_loss_value=round(stop_loss, 6),
            maximum_loss_value=round(max_loss_value, 6),
            time_exit_dte=self.policy.exit_days_to_expiration,
            event_risk_exit_days=self.policy.event_risk_exit_days,
            expiration_exit_required=True,
            close_order_type="LIMIT",
            monitoring_frequency=(
                "INTRADAY"
                if dte <= self.policy.adjustment_days_to_expiration
                or event_risk_exit_required
                else "DAILY"
            ),
        )

        adjustments: list[AdjustmentActionProfile] = []
        adjustments.append(
            AdjustmentActionProfile(
                action="ROLL_OUT",
                priority=1,
                trigger=(
                    f"DTE <= {self.policy.adjustment_days_to_expiration} "
                    "and thesis remains valid"
                ),
                allowed=self.policy.allow_rolls and defined_risk,
                target="Restore preferred duration and improve basis.",
                rationale=(
                    "Extend duration before gamma acceleration becomes dominant."
                ),
            )
        )
        adjustments.append(
            AdjustmentActionProfile(
                action="REDUCE_SIZE",
                priority=2,
                trigger=(
                    f"Loss >= {self.policy.adjustment_loss_trigger_pct:.0%} "
                    "of maximum loss"
                ),
                allowed=self.policy.allow_reduce_size,
                target="Reduce portfolio and position risk.",
                rationale="De-risk while retaining partial thesis exposure.",
            )
        )
        adjustments.append(
            AdjustmentActionProfile(
                action="DELTA_HEDGE",
                priority=3,
                trigger=(
                    f"Absolute delta exposure >= "
                    f"{self.policy.delta_adjustment_trigger:.2f}"
                ),
                allowed=(
                    self.policy.allow_hedges
                    and abs(current_delta_exposure)
                    >= self.policy.delta_adjustment_trigger
                ),
                target="Return delta exposure toward neutral.",
                rationale="Control directional drift and tail acceleration.",
            )
        )
        adjustments.append(
            AdjustmentActionProfile(
                action="CLOSE_POSITION",
                priority=4,
                trigger=(
                    "Profit target, stop loss, event-risk exit, "
                    "or time exit is reached"
                ),
                allowed=True,
                target="Terminate exposure according to governance.",
                rationale="Preserve capital and avoid unmanaged expiration risk.",
            )
        )

        checkpoints = (
            LifecycleCheckpointProfile(
                name="ENTRY_CONFIRMATION",
                trigger_condition="Before order submission",
                recommended_action=(
                    "Revalidate liquidity, confidence, event risk, "
                    "and defined-risk status."
                ),
                severity="HIGH",
                mandatory=True,
            ),
            LifecycleCheckpointProfile(
                name="PROFIT_TARGET",
                trigger_condition=(
                    f"Open profit >= {profit_target:.2f}"
                ),
                recommended_action="Close or scale out.",
                severity="MEDIUM",
                mandatory=False,
            ),
            LifecycleCheckpointProfile(
                name="LOSS_REVIEW",
                trigger_condition=(
                    f"Open loss >= {stop_loss:.2f}"
                ),
                recommended_action="Close, reduce, or adjust immediately.",
                severity="HIGH",
                mandatory=True,
            ),
            LifecycleCheckpointProfile(
                name="TIME_EXIT",
                trigger_condition=(
                    f"DTE <= {self.policy.exit_days_to_expiration}"
                ),
                recommended_action="Close before expiration-risk window.",
                severity="HIGH",
                mandatory=True,
            ),
            LifecycleCheckpointProfile(
                name="EVENT_RISK",
                trigger_condition=(
                    f"Material event within "
                    f"{self.policy.event_risk_exit_days} days"
                ),
                recommended_action="Close, hedge, or explicitly approve risk.",
                severity="HIGH",
                mandatory=True,
            ),
        )

        passed_components = 0
        total_components = 5
        passed_components += int(entry_allowed)
        passed_components += int(
            self.policy.preferred_entry_dte_min
            <= dte
            <= self.policy.preferred_entry_dte_max
        )
        passed_components += int(
            confidence >= self.policy.minimum_entry_confidence
        )
        passed_components += int(
            spread_pct <= self.policy.maximum_entry_spread_pct
        )
        passed_components += int(
            defined_risk or not self.policy.require_defined_risk
        )
        score = round(
            passed_components / total_components * 100.0,
            6,
        )

        return TradeLifecycleProfile(
            symbol=symbol,
            strategy_name=strategy_name,
            entry=entry,
            exit=exit_plan,
            adjustments=tuple(adjustments),
            checkpoints=checkpoints,
            lifecycle_score=score,
            lifecycle_grade=self._grade(score),
            risk_severity=self._severity(
                len(rejections),
                len(warnings),
            ),
            allowed=entry_allowed,
            warnings=tuple(dict.fromkeys(warnings)),
            rejection_reasons=tuple(dict.fromkeys(rejections)),
            metadata={
                "milestone": 34,
                "phase": 3,
                "step": 3,
                "source": "TRADE_LIFECYCLE_PLANNING",
            },
        )
