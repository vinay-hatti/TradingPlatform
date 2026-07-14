from dataclasses import dataclass, field
from typing import Any


@dataclass
class MarketRegimeGovernanceProfile:
    valid: bool = False
    allowed: bool = False
    recommendation: str = "RETAIN_CHAMPION"
    champion_version: str = "UNAVAILABLE"
    challenger_version: str = "UNAVAILABLE"
    evaluation_observation_count: int = 0
    champion_accuracy: float = 0.0
    challenger_accuracy: float = 0.0
    accuracy_improvement: float = 0.0
    forecast_accuracy_improvement: float = 0.0
    transition_f1_improvement: float = 0.0
    critical_false_positive_deterioration: float = 0.0
    champion_score: float = 0.0
    challenger_score: float = 0.0
    promotion_eligible: bool = False
    promotion_applied: bool = False
    confidence_score: float = 0.0
    governance_grade: str = "N/A"
    risk_severity: str = "UNKNOWN"
    drift_profile: Any = None
    warnings: list[str] = field(default_factory=list)
    rejection_reasons: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
