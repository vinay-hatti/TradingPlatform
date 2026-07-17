from __future__ import annotations

from typing import Any

from .broker_reconciliation_policy import BrokerReconciliationPolicy
from .broker_status_profile import (
    BrokerPositionProfile,
    BrokerReconciliationSummary,
    PositionReconciliationCheck,
    PositionReconciliationProfile,
)


class BrokerPositionReconciliationEngine:
    def __init__(
        self,
        policy: BrokerReconciliationPolicy | None = None,
    ) -> None:
        self.policy = policy or BrokerReconciliationPolicy()
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

    def reconcile_position(
        self,
        broker_position: BrokerPositionProfile | None,
        platform_position: BrokerPositionProfile | None,
    ) -> PositionReconciliationProfile:
        checks: list[PositionReconciliationCheck] = []

        def add(
            name: str,
            passed: bool,
            message: str,
            *,
            required: bool = True,
            metadata: dict[str, Any] | None = None,
        ) -> None:
            checks.append(
                PositionReconciliationCheck(
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
            "broker_position",
            broker_position is not None,
            "Broker position is available.",
            required=self.policy.require_position_match,
        )
        add(
            "platform_position",
            platform_position is not None,
            "Platform position is available.",
            required=self.policy.require_position_match,
        )

        symbol = (
            broker_position.symbol
            if broker_position is not None
            else platform_position.symbol
            if platform_position is not None
            else ""
        )
        account_id = (
            broker_position.account_id
            if broker_position is not None
            else platform_position.account_id
            if platform_position is not None
            else ""
        )

        quantity_difference = None
        average_cost_difference = None
        average_cost_difference_pct = None

        if broker_position is not None and platform_position is not None:
            add(
                "symbol_match",
                broker_position.symbol == platform_position.symbol,
                "Broker and platform symbols match.",
            )
            add(
                "account_match",
                broker_position.account_id == platform_position.account_id,
                "Broker and platform accounts match.",
            )

            quantity_difference = (
                broker_position.quantity - platform_position.quantity
            )
            add(
                "quantity_match",
                abs(quantity_difference)
                <= self.policy.maximum_position_quantity_difference,
                "Position quantities are within tolerance.",
                metadata={"difference": quantity_difference},
            )

            average_cost_difference = (
                broker_position.average_cost
                - platform_position.average_cost
            )
            denominator = abs(platform_position.average_cost)
            average_cost_difference_pct = (
                abs(average_cost_difference) / denominator
                if denominator > 0
                else 0.0
            )
            add(
                "average_cost_match",
                average_cost_difference_pct
                <= self.policy.maximum_cost_basis_difference_pct,
                "Position average costs are within tolerance.",
                metadata={
                    "difference": average_cost_difference,
                    "difference_pct": average_cost_difference_pct,
                },
            )

        required = [check for check in checks if check.required]
        failed = [check for check in required if not check.passed]
        score = (
            sum(check.score for check in required) / len(required)
            if required else 100.0
        )
        allowed = (
            not failed
            and score >= self.policy.minimum_reconciliation_score
        )
        if not self.policy.fail_closed:
            allowed = score >= self.policy.minimum_reconciliation_score

        grade, severity = self._grade(score)
        return PositionReconciliationProfile(
            valid=True,
            allowed=allowed,
            account_id=account_id,
            symbol=symbol,
            score=round(score, 2),
            grade=grade,
            severity=severity,
            recommendation="ACCEPT" if allowed else "RECONCILE",
            broker_position=broker_position,
            platform_position=platform_position,
            quantity_difference=quantity_difference,
            average_cost_difference=average_cost_difference,
            average_cost_difference_pct=average_cost_difference_pct,
            checks=tuple(checks),
            rejection_reasons=tuple(
                check.name.upper() for check in failed
            ),
        )

    def reconcile_many(
        self,
        broker_positions: tuple[BrokerPositionProfile, ...],
        platform_positions: tuple[BrokerPositionProfile, ...],
        *,
        order_summaries=(),
        fill_count: int = 0,
    ) -> BrokerReconciliationSummary:
        broker_map = {
            (position.account_id, position.symbol): position
            for position in broker_positions
        }
        platform_map = {
            (position.account_id, position.symbol): position
            for position in platform_positions
        }
        keys = sorted(set(broker_map) | set(platform_map))

        profiles = tuple(
            self.reconcile_position(
                broker_map.get(key),
                platform_map.get(key),
            )
            for key in keys
        )
        matched = sum(profile.allowed for profile in profiles)
        rejected = len(profiles) - matched
        score = (
            sum(profile.score for profile in profiles) / len(profiles)
            if profiles else 100.0
        )
        grade, severity = self._grade(score)
        allowed = rejected == 0

        return BrokerReconciliationSummary(
            valid=True,
            allowed=allowed,
            order_count=len(tuple(order_summaries)),
            fill_count=fill_count,
            position_count=len(profiles),
            matched_position_count=matched,
            rejected_position_count=rejected,
            score=round(score, 2),
            grade=grade,
            severity=severity,
            recommendation="ACCEPT" if allowed else "RECONCILE",
            order_summaries=tuple(order_summaries),
            position_profiles=profiles,
            rejection_reasons=tuple(
                f"{profile.symbol}:{reason}"
                for profile in profiles
                for reason in profile.rejection_reasons
            ),
        )
