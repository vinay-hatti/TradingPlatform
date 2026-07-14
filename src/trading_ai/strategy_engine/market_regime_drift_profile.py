from dataclasses import dataclass, field
from typing import Any


@dataclass
class MarketRegimeDriftProfile:
    valid: bool = False
    allowed: bool = True
    reference_observation_count: int = 0
    recent_observation_count: int = 0
    regime_population_stability_index: float = 0.0
    regime_score_shift: float = 0.0
    confidence_shift: float = 0.0
    transition_rate_shift: float = 0.0
    reference_regime_distribution: dict[str, float] = field(default_factory=dict)
    recent_regime_distribution: dict[str, float] = field(default_factory=dict)
    drift_score: float = 0.0
    drift_grade: str = "N/A"
    drift_severity: str = "UNKNOWN"
    warnings: list[str] = field(default_factory=list)
    rejection_reasons: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
