from __future__ import annotations

from .paper_trading_policy import PaperTradingAutomationPolicy
from .paper_trading_profile import (
    PaperTradingCheck,
    PaperTradingRuntimeState,
    PaperTradingSessionDecision,
    PaperTradingSessionProfile,
)


class PaperTradingSessionEngine:
    def __init__(
        self,
        policy: PaperTradingAutomationPolicy | None = None,
    ) -> None:
        self.policy = policy or PaperTradingAutomationPolicy()
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

    def create(
        self,
        profile: PaperTradingSessionProfile,
    ) -> tuple[PaperTradingSessionDecision, PaperTradingRuntimeState | None]:
        checks: list[PaperTradingCheck] = []

        def add(name: str, passed: bool, message: str) -> None:
            checks.append(
                PaperTradingCheck(
                    name=name,
                    passed=bool(passed),
                    required=True,
                    score=100.0 if passed else 0.0,
                    severity="LOW" if passed else "CRITICAL",
                    message=message,
                )
            )

        add("session_id", bool(profile.session_id), "Session id is required.")
        add("account_id", bool(profile.account_id), "Account id is required.")
        add(
            "environment",
            profile.environment.lower() in self.policy.allowed_environments,
            "Session environment is allowed.",
        )
        add(
            "strategy_names",
            bool(profile.strategy_names),
            "At least one strategy is required.",
        )
        add(
            "symbols",
            bool(profile.symbols),
            "At least one symbol is required.",
        )
        add(
            "cycle_interval",
            self.policy.minimum_cycle_interval_seconds
            <= profile.cycle_interval_seconds
            <= self.policy.maximum_cycle_interval_seconds,
            "Cycle interval is within policy.",
        )
        add(
            "starting_capital",
            profile.starting_capital > 0,
            "Starting capital must be positive.",
        )
        add(
            "initial_state",
            profile.state == "CREATED",
            "New sessions must begin in CREATED state.",
        )

        failed = [check for check in checks if not check.passed]
        score = (
            sum(check.score for check in checks) / len(checks)
            if checks else 100.0
        )
        allowed = not failed
        grade, severity = self._grade(score)

        decision = PaperTradingSessionDecision(
            valid=True,
            allowed=allowed,
            action="CREATE",
            session_id=profile.session_id,
            current_state=profile.state,
            target_state="CREATED" if allowed else None,
            score=round(score, 2),
            grade=grade,
            severity=severity,
            recommendation="CREATE" if allowed else "REJECT",
            checks=tuple(checks),
            rejection_reasons=tuple(
                check.name.upper() for check in failed
            ),
        )
        if not allowed:
            return decision, None

        return decision, PaperTradingRuntimeState(session=profile)
