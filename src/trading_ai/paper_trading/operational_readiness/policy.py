from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class OperationalReadinessPolicy:
    environment: str = "PAPER"
    live_trading_enabled: bool = False
    minimum_overall_score: float = 85.0
    minimum_category_score: float = 75.0
    maximum_failed_controls: int = 0
    maximum_warning_controls: int = 8
    require_phase_reports: tuple[int, ...] = tuple(range(1, 9))
    require_kill_switch_control: bool = True
    require_duplicate_run_control: bool = True
    require_recovery_control: bool = True
    require_observability_control: bool = True
    require_paper_broker: bool = True

    def validate(self) -> None:
        if self.environment != "PAPER":
            raise ValueError("operational readiness must remain PAPER")
        if self.live_trading_enabled:
            raise ValueError("live trading cannot be enabled")
        if not 0 <= self.minimum_overall_score <= 100:
            raise ValueError("minimum_overall_score must be within [0, 100]")
        if not 0 <= self.minimum_category_score <= 100:
            raise ValueError("minimum_category_score must be within [0, 100]")
        if self.maximum_failed_controls < 0:
            raise ValueError("maximum_failed_controls cannot be negative")
        if self.maximum_warning_controls < 0:
            raise ValueError("maximum_warning_controls cannot be negative")
