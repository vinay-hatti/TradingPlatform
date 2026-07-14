from dataclasses import dataclass, field
from typing import Any

@dataclass
class MarketRegimeIntegrationProfile:
    symbol: str = ""
    current_regime: str = "UNKNOWN"
    forecast_regime: str = "UNKNOWN"
    portfolio_regime: str = "UNKNOWN"
    regime_score: float = 0.0
    forecast_score: float = 0.0
    breadth_score: float = 0.0
    confidence_score: float = 0.0
    strategy_score_adjustment: float = 0.0
    ranking_score_adjustment: float = 0.0
    adapted_strategy_score: float = 0.0
    adapted_ranking_score: float = 0.0
    strategy_alignment: str = "NEUTRAL"
    transition_risk: float = 0.0
    allowed: bool = True
    valid: bool = False
    grade: str = "N/A"
    severity: str = "UNKNOWN"
    warnings: list[str] = field(default_factory=list)
    rejection_reasons: list[str] = field(default_factory=list)
    regime_profile: Any = None
    forecast_profile: Any = None
    breadth_profile: Any = None
    metadata: dict = field(default_factory=dict)
