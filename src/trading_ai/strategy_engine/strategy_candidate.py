from dataclasses import dataclass, field


@dataclass
class StrategyCandidate:
    symbol: str
    direction: str
    strategy: str

    volatility_regime: str
    volatility_signal: str
    market_regime: str

    score: float
    confidence: float

    reason: str
    risk_profile: str
    premium_type: str

    allowed: bool = True
    warnings: list[str] = field(default_factory=list)
