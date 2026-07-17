from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SLOPolicy:
    evaluation_window_seconds: float = 3600.0
    minimum_sample_count: int = 1
    default_target: float = 0.99
    fail_closed_on_insufficient_data: bool = True

    def validate(self) -> None:
        if self.evaluation_window_seconds <= 0:
            raise ValueError("evaluation_window_seconds must be positive")
        if self.minimum_sample_count <= 0:
            raise ValueError("minimum_sample_count must be positive")
        if not 0 < self.default_target <= 1:
            raise ValueError("default_target must be in (0, 1]")


@dataclass(frozen=True)
class ErrorBudgetPolicy:
    fast_burn_threshold: float = 14.4
    slow_burn_threshold: float = 6.0
    exhaustion_threshold: float = 1.0
    reset_period_seconds: float = 2592000.0

    def validate(self) -> None:
        if self.fast_burn_threshold <= 0:
            raise ValueError("fast_burn_threshold must be positive")
        if self.slow_burn_threshold <= 0:
            raise ValueError("slow_burn_threshold must be positive")
        if not 0 <= self.exhaustion_threshold <= 1:
            raise ValueError(
                "exhaustion_threshold must be between 0 and 1"
            )
        if self.reset_period_seconds <= 0:
            raise ValueError("reset_period_seconds must be positive")
