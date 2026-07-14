from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class WalkForwardEvaluationResult:
    """Normalized evaluator output consumed by the institutional walk-forward engine."""

    score: float = 0.0
    return_pct: float = 0.0
    sharpe: float = 0.0
    max_drawdown_pct: float = 0.0
    observation_count: int = 0
    trade_count: int = 0
    valid: bool = True
    warnings: list[str] = field(default_factory=list)
    rejection_reasons: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def as_engine_metrics(self) -> dict[str, float]:
        return {
            "score": float(self.score),
            "return": float(self.return_pct),
            "sharpe": float(self.sharpe),
            "max_drawdown_pct": abs(float(self.max_drawdown_pct)),
        }


@dataclass
class WalkForwardAdapterDiagnostics:
    """Audit information for an adapter-backed walk-forward run."""

    adapter_name: str
    evaluation_count: int = 0
    successful_evaluations: int = 0
    failed_evaluations: int = 0
    parameter_sets_seen: int = 0
    warnings: list[str] = field(default_factory=list)
    rejection_reasons: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
