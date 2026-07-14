from dataclasses import dataclass, field
from typing import Any


@dataclass
class WalkForwardGovernanceProfile:
    valid: bool = False
    allowed: bool = False
    recommendation: str = "RETAIN_CHAMPION"
    champion_version: str = "UNAVAILABLE"
    challenger_version: str = "UNAVAILABLE"
    champion_score: float = 0.0
    challenger_score: float = 0.0
    score_improvement: float = 0.0
    oos_return_improvement: float = 0.0
    sharpe_improvement: float = 0.0
    drawdown_deterioration_pct: float = 0.0
    degradation_deterioration_pct: float = 0.0
    promotion_eligible: bool = False
    promotion_applied: bool = False
    confidence_score: float = 0.0
    governance_grade: str = "N/A"
    risk_severity: str = "UNKNOWN"
    champion_profile: Any = None
    challenger_profile: Any = None
    warnings: list[str] = field(default_factory=list)
    rejection_reasons: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
