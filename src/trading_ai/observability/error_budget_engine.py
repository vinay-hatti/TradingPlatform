from __future__ import annotations

from .slo_policy import ErrorBudgetPolicy
from .slo_profile import ErrorBudgetEvaluation, SLOEvaluation


class ErrorBudgetEngine:
    def __init__(
        self,
        policy: ErrorBudgetPolicy | None = None,
    ) -> None:
        self.policy = policy or ErrorBudgetPolicy()
        self.policy.validate()

    def evaluate(
        self,
        slo: SLOEvaluation,
    ) -> ErrorBudgetEvaluation:
        allowed_bad = max(0.0, 1.0 - slo.target)
        observed_bad = max(0.0, 1.0 - slo.observed)
        consumed = (
            observed_bad / allowed_bad if allowed_bad > 0 else (
                float("inf") if observed_bad > 0 else 0.0
            )
        )
        remaining = max(0.0, 1.0 - consumed)
        burn_rate = consumed
        exhausted = consumed >= self.policy.exhaustion_threshold
        fast_burn = burn_rate >= self.policy.fast_burn_threshold
        slow_burn = burn_rate >= self.policy.slow_burn_threshold
        if fast_burn:
            recommendation = "PAGE_FAST_BURN"
        elif slow_burn:
            recommendation = "ALERT_SLOW_BURN"
        elif exhausted:
            recommendation = "FREEZE_RISKY_CHANGES"
        else:
            recommendation = "BUDGET_HEALTHY"
        return ErrorBudgetEvaluation(
            slo_id=slo.slo_id,
            allowed_bad_fraction=allowed_bad,
            observed_bad_fraction=observed_bad,
            consumed_fraction=consumed,
            remaining_fraction=remaining,
            burn_rate=burn_rate,
            exhausted=exhausted,
            fast_burn=fast_burn,
            slow_burn=slow_burn,
            recommendation=recommendation,
        )
