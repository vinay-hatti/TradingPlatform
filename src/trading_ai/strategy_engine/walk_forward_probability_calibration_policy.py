from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class WalkForwardProbabilityCalibrationPolicy:
    """Controls rolling calibration retraining and out-of-sample evaluation."""

    minimum_train_observations: int = 250
    minimum_validation_observations: int = 75
    minimum_test_observations: int = 75
    minimum_completed_windows: int = 3
    minimum_oos_brier_improvement: float = -0.02
    minimum_oos_log_loss_improvement: float = -0.02
    maximum_oos_ece: float = 0.15
    maximum_oos_mce: float = 0.30
    maximum_model_score_degradation: float = 0.40
    minimum_segment_coverage: float = 0.50
    register_window_models: bool = False
    activate_latest_model: bool = False
    retrain_on_train_and_validation: bool = True
    reject_critical_calibration: bool = True
    objective_weights: dict[str, float] = field(default_factory=lambda: {
        "brier": 0.35,
        "log_loss": 0.25,
        "ece": 0.20,
        "coverage": 0.10,
        "model_score": 0.10,
    })

    def validate(self) -> None:
        for name in (
            "minimum_train_observations",
            "minimum_validation_observations",
            "minimum_test_observations",
            "minimum_completed_windows",
        ):
            if int(getattr(self, name)) <= 0:
                raise ValueError(f"{name} must be positive")
        for name in (
            "maximum_oos_ece",
            "maximum_oos_mce",
            "maximum_model_score_degradation",
            "minimum_segment_coverage",
        ):
            value = float(getattr(self, name))
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"{name} must be between 0 and 1")
        if sum(self.objective_weights.values()) <= 0:
            raise ValueError("objective_weights must have positive total weight")
