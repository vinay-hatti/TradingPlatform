from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class WalkForwardPolicy:
    """Institutional rolling-window validation controls."""

    train_size: int = 252
    validation_size: int = 63
    test_size: int = 63
    step_size: int = 63
    anchored_training: bool = False
    purge_size: int = 5
    embargo_size: int = 5
    minimum_windows: int = 3
    minimum_train_observations: int = 120
    minimum_validation_observations: int = 30
    minimum_test_observations: int = 30
    minimum_oos_sharpe: float = 0.0
    maximum_oos_drawdown_pct: float = 0.30
    maximum_degradation_pct: float = 0.50
    minimum_parameter_stability_score: float = 50.0
    reject_critical_instability: bool = True
    objective_weights: dict[str, float] = field(default_factory=lambda: {
        "return": 0.30,
        "sharpe": 0.25,
        "drawdown": 0.20,
        "stability": 0.15,
        "consistency": 0.10,
    })

    def __post_init__(self) -> None:
        positive = {
            "train_size": self.train_size,
            "validation_size": self.validation_size,
            "test_size": self.test_size,
            "step_size": self.step_size,
            "minimum_windows": self.minimum_windows,
        }
        for name, value in positive.items():
            if value <= 0:
                raise ValueError(f"{name} must be positive")
        if self.purge_size < 0 or self.embargo_size < 0:
            raise ValueError("purge_size and embargo_size cannot be negative")
        if not 0.0 <= self.maximum_oos_drawdown_pct <= 1.0:
            raise ValueError("maximum_oos_drawdown_pct must be between 0 and 1")
        if not 0.0 <= self.maximum_degradation_pct <= 1.0:
            raise ValueError("maximum_degradation_pct must be between 0 and 1")
