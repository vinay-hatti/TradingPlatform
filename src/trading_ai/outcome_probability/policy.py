from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class OutcomeProbabilityPolicy:
    """Fail-closed M77 policy. M77 never changes live ranking or trade authority."""

    horizon_sessions: int = 30
    entry_window_sessions: int = 5
    minimum_training_samples: int = 500
    minimum_positive_samples: int = 75
    minimum_negative_samples: int = 75
    minimum_distinct_as_of_dates: int = 140
    maximum_test_brier: float = 0.25
    maximum_test_ece: float = 0.10
    minimum_test_auc: float = 0.55
    minimum_target_1_probability: float = 0.65
    minimum_profitable_probability: float = 0.55
    minimum_expected_value_r: float = 0.10
    maximum_trade_uncertainty: float = 0.30
    maximum_trade_ood_score: float = 0.70
    analog_limit: int = 25
    minimum_analogs: int = 20
    materialization_batch_size: int = 5000
    automatic_activation: bool = False
    runtime_mode: str = "SHADOW"

    def validate(self) -> None:
        if self.horizon_sessions < 5:
            raise ValueError("horizon_sessions must be at least 5")
        if not 1 <= self.entry_window_sessions < self.horizon_sessions:
            raise ValueError("entry_window_sessions must be inside the horizon")
        if self.runtime_mode != "SHADOW":
            raise ValueError("M77.0 runtime_mode must remain SHADOW")
        if self.automatic_activation:
            raise ValueError("M77.0 forbids automatic model activation")
        if self.materialization_batch_size < 1:
            raise ValueError("materialization_batch_size must be positive")
