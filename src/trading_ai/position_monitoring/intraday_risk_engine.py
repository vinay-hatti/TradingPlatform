from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .mark_to_market_engine import MarkToMarketEngine
from .position_monitoring_policy import PositionMonitoringPolicy
from .position_monitoring_profile import (
    PositionSnapshotCheck,
    PositionSnapshotDecision,
    RealTimePositionSnapshot,
    RealTimeQuoteSnapshot,
)


class IntradayRiskStateEngine:
    def __init__(
        self,
        policy: PositionMonitoringPolicy | None = None,
    ) -> None:
        self.policy = policy or PositionMonitoringPolicy()
        self.policy.validate()
        self.mark_to_market = MarkToMarketEngine(self.policy)

    @staticmethod
    def _grade(score: float) -> tuple[str, str]:
        if score >= 95:
            return "A", "LOW"
        if score >= 85:
            return "B", "MODERATE"
        if score >= 70:
            return "C", "SEVERE"
        return "F", "CRITICAL"

    def evaluate(
        self,
        *,
        account_id: str,
        starting_equity: float,
        peak_equity: float,
        cash_balance: float,
        positions: tuple[RealTimePositionSnapshot, ...],
        quotes: dict[str, RealTimeQuoteSnapshot],
        as_of: datetime | None = None,
        snapshot_id: str | None = None,
    ) -> PositionSnapshotDecision:
        now = as_of or datetime.now(timezone.utc)
        checks: list[PositionSnapshotCheck] = []

        def add(
            name: str,
            passed: bool,
            message: str,
            *,
            required: bool = True,
            metadata: dict[str, Any] | None = None,
        ) -> None:
            checks.append(
                PositionSnapshotCheck(
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
            "position_count",
            len(positions) <= self.policy.maximum_positions_per_snapshot,
            "Position count is within policy.",
        )
        position_ids = [position.position_id for position in positions]
        add(
            "duplicate_position_ids",
            not self.policy.reject_duplicate_position_ids
            or len(position_ids) == len(set(position_ids)),
            "Position ids are unique.",
        )
        add(
            "account_consistency",
            not self.policy.require_account_consistency
            or all(position.account_id == account_id for position in positions),
            "All positions belong to the requested account.",
        )
        add(
            "starting_equity",
            starting_equity >= 0
            or not self.policy.require_non_negative_starting_equity,
            "Starting equity is non-negative.",
        )

        missing_symbols = tuple(
            position.symbol
            for position in positions
            if position.symbol not in quotes
        )
        add(
            "quote_coverage",
            not missing_symbols or not self.policy.reject_missing_quotes,
            "All positions have market quotes.",
            required=self.policy.reject_missing_quotes,
            metadata={"missing_symbols": missing_symbols},
        )

        stale_symbols = tuple(
            position.symbol
            for position in positions
            if position.symbol in quotes
            and self.mark_to_market.quote_is_stale(
                quotes[position.symbol],
                as_of=now,
            )
        )
        add(
            "quote_freshness",
            not stale_symbols or not self.policy.reject_stale_quotes,
            "All position quotes are fresh.",
            required=self.policy.reject_stale_quotes,
            metadata={"stale_symbols": stale_symbols},
        )

        required_checks = [check for check in checks if check.required]
        failed = [check for check in required_checks if not check.passed]
        score = (
            sum(check.score for check in required_checks)
            / len(required_checks)
            if required_checks
            else 100.0
        )

        risk_state = None
        if not failed or not self.policy.fail_closed:
            risk_state = self.mark_to_market.aggregate(
                account_id=account_id,
                starting_equity=starting_equity,
                peak_equity=peak_equity,
                cash_balance=cash_balance,
                positions=positions,
                quotes=quotes,
                as_of=now,
                snapshot_id=snapshot_id,
            )

        allowed = (
            not failed
            and score >= self.policy.minimum_snapshot_score
            and risk_state is not None
        )
        if not self.policy.fail_closed:
            allowed = (
                score >= self.policy.minimum_snapshot_score
                and risk_state is not None
            )

        grade, severity = self._grade(score)
        return PositionSnapshotDecision(
            valid=True,
            allowed=allowed,
            account_id=account_id,
            snapshot_id=(
                risk_state.snapshot_id
                if risk_state is not None
                else snapshot_id or "UNAVAILABLE"
            ),
            score=round(score, 2),
            grade=grade,
            severity=severity,
            recommendation="PUBLISH" if allowed else "REJECT",
            risk_state=risk_state,
            checks=tuple(checks),
            warnings=tuple(
                f"STALE_QUOTE:{symbol}" for symbol in stale_symbols
            ),
            rejection_reasons=tuple(
                check.name.upper() for check in failed
            ),
            metadata={
                "missing_symbols": missing_symbols,
                "stale_symbols": stale_symbols,
            },
        )
