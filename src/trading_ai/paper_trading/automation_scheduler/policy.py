from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AutomationSchedulerPolicy:
    environment: str = "PAPER"
    live_trading_enabled: bool = False
    kill_switch_active: bool = False
    prevent_duplicate_runs: bool = True
    maximum_run_age_minutes: int = 120
    maximum_total_errors: int = 0
    maximum_total_warnings: int = 25
    stop_on_required_phase_failure: bool = True
    continue_on_optional_phase_failure: bool = True
    maximum_phase_attempts: int = 2
    default_timeout_seconds: int = 900
    allowed_modes: tuple[str, ...] = ("DRY_RUN", "MONITOR_ONLY", "SUBMIT")
    submit_confirmation_template: str = (
        "RUN SCHEDULED PAPER AUTOMATION {portfolio_id} {run_key}"
    )

    def validate(self) -> None:
        if self.environment != "PAPER":
            raise ValueError("scheduler must remain PAPER")
        if self.live_trading_enabled:
            raise ValueError("live trading cannot be enabled")
        if self.maximum_run_age_minutes < 1:
            raise ValueError("maximum_run_age_minutes must be positive")
        if self.maximum_total_errors < 0:
            raise ValueError("maximum_total_errors cannot be negative")
        if self.maximum_total_warnings < 0:
            raise ValueError("maximum_total_warnings cannot be negative")
        if self.maximum_phase_attempts < 1:
            raise ValueError("maximum_phase_attempts must be positive")
        if self.default_timeout_seconds < 1:
            raise ValueError("default_timeout_seconds must be positive")
