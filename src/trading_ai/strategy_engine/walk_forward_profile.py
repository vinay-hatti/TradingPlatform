from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class WalkForwardWindow:
    window_id: str
    train_start: int
    train_end: int
    validation_start: int
    validation_end: int
    test_start: int
    test_end: int
    purge_size: int = 0
    embargo_size: int = 0

    @property
    def train_count(self) -> int:
        return max(0, self.train_end - self.train_start)

    @property
    def validation_count(self) -> int:
        return max(0, self.validation_end - self.validation_start)

    @property
    def test_count(self) -> int:
        return max(0, self.test_end - self.test_start)


@dataclass
class WalkForwardWindowResult:
    window_id: str
    selected_parameters: dict[str, Any] = field(default_factory=dict)
    train_score: float = 0.0
    validation_score: float = 0.0
    test_score: float = 0.0
    train_return: float = 0.0
    validation_return: float = 0.0
    test_return: float = 0.0
    train_sharpe: float = 0.0
    validation_sharpe: float = 0.0
    test_sharpe: float = 0.0
    test_max_drawdown_pct: float = 0.0
    degradation_pct: float = 0.0
    valid: bool = True
    warnings: list[str] = field(default_factory=list)
    rejection_reasons: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class WalkForwardProfile:
    valid: bool = False
    allowed: bool = False
    window_count: int = 0
    completed_window_count: int = 0
    aggregate_oos_return: float = 0.0
    average_oos_sharpe: float = 0.0
    worst_oos_drawdown_pct: float = 0.0
    average_degradation_pct: float = 0.0
    parameter_stability_score: float = 0.0
    window_consistency_score: float = 0.0
    walk_forward_score: float = 0.0
    walk_forward_grade: str = "N/A"
    risk_severity: str = "UNKNOWN"
    windows: list[WalkForwardWindow] = field(default_factory=list)
    results: list[WalkForwardWindowResult] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    rejection_reasons: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
