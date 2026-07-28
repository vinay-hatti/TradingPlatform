from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AutomationObservabilityPolicy:
    environment: str = "PAPER"
    live_trading_enabled: bool = False
    minimum_portfolio_health_score: float = 70.0
    maximum_stale_orders: int = 0
    maximum_failed_phases: int = 0
    maximum_cycle_errors: int = 0
    maximum_cycle_warnings: int = 20
    maximum_risk_breaches: int = 0
    maximum_retried_phases: int = 3
    critical_daily_loss_pct: float = 3.0
    unhealthy_score_threshold: float = 60.0
    degraded_score_threshold: float = 80.0

    def validate(self) -> None:
        if self.environment != "PAPER":
            raise ValueError("observability must remain PAPER")
        if self.live_trading_enabled:
            raise ValueError("live trading cannot be enabled")
        if not 0.0 <= self.minimum_portfolio_health_score <= 100.0:
            raise ValueError(
                "minimum_portfolio_health_score must be within [0, 100]"
            )
        if not 0.0 <= self.unhealthy_score_threshold <= 100.0:
            raise ValueError("unhealthy_score_threshold must be within [0, 100]")
        if not 0.0 <= self.degraded_score_threshold <= 100.0:
            raise ValueError("degraded_score_threshold must be within [0, 100]")
        if self.unhealthy_score_threshold > self.degraded_score_threshold:
            raise ValueError(
                "unhealthy_score_threshold cannot exceed degraded threshold"
            )
        for name in (
            "maximum_stale_orders",
            "maximum_failed_phases",
            "maximum_cycle_errors",
            "maximum_cycle_warnings",
            "maximum_risk_breaches",
            "maximum_retried_phases",
        ):
            if int(getattr(self, name)) < 0:
                raise ValueError(f"{name} cannot be negative")
