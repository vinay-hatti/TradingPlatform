from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class MarketBreadthContribution:
    symbol: str
    regime: str
    weight: float
    bullish: bool
    bearish: bool
    stressed: bool
    confidence_score: float = 0.0
    regime_score: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class MarketBreadthProfile:
    symbol_count: int = 0
    total_weight: float = 0.0
    dominant_regime: str = "UNKNOWN"
    portfolio_regime: str = "UNKNOWN"
    bullish_breadth: float = 0.0
    bearish_breadth: float = 0.0
    neutral_breadth: float = 0.0
    stress_breadth: float = 0.0
    regime_dispersion: float = 0.0
    score_dispersion: float = 0.0
    confidence_dispersion: float = 0.0
    concentration_score: float = 0.0
    effective_symbol_count: float = 0.0
    agreement_score: float = 0.0
    breadth_score: float = 0.0
    breadth_grade: str = "N/A"
    breadth_severity: str = "UNKNOWN"
    allowed: bool = True
    valid: bool = False
    regime_weights: Dict[str, float] = field(default_factory=dict)
    contributions: List[MarketBreadthContribution] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    rejection_reasons: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def score(self) -> float:
        return self.breadth_score

    @property
    def grade(self) -> str:
        return self.breadth_grade

    @property
    def severity(self) -> str:
        return self.breadth_severity
