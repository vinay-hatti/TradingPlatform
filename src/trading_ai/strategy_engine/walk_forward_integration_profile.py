from dataclasses import dataclass, field
from typing import Any


@dataclass
class WalkForwardIntegrationProfile:
    valid: bool = False
    allowed: bool = True
    source: str = "UNAVAILABLE"
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
    raw_profile: Any = None
    warnings: list[str] = field(default_factory=list)
    rejection_reasons: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
