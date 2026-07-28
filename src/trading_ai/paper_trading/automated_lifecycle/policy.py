from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AutomatedOrderLifecyclePolicy:
    environment: str = "PAPER"
    live_trading_enabled: bool = False
    automatic_cancellation_enabled: bool = False
    stale_submitted_minutes: int = 30
    stale_partial_fill_minutes: int = 60
    maximum_cancel_actions_per_run: int = 10
    terminal_states: tuple[str, ...] = (
        "FILLED",
        "CANCELED",
        "CANCELLED",
        "REJECTED",
        "INACTIVE",
        "APICANCELLED",
    )
    active_states: tuple[str, ...] = (
        "PRESUBMITTED",
        "SUBMITTED",
        "PENDINGSUBMIT",
        "PENDINGCANCEL",
        "CANCEL_REQUESTED",
        "PARTIALLY_FILLED",
    )
    cancellation_confirmation_template: str = (
        "CANCEL STALE IBKR PAPER ORDERS {portfolio_id}"
    )

    def validate(self) -> None:
        if self.environment != "PAPER":
            raise ValueError("lifecycle policy must remain PAPER")
        if self.live_trading_enabled:
            raise ValueError("live trading cannot be enabled")
        if self.stale_submitted_minutes < 1:
            raise ValueError("stale_submitted_minutes must be positive")
        if self.stale_partial_fill_minutes < self.stale_submitted_minutes:
            raise ValueError(
                "partial-fill stale threshold cannot be below submitted threshold"
            )
        if self.maximum_cancel_actions_per_run < 1:
            raise ValueError("maximum_cancel_actions_per_run must be positive")
