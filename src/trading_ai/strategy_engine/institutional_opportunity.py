from dataclasses import dataclass, field
from typing import Any


@dataclass
class InstitutionalOpportunity:
    """
    Complete options opportunity prepared for institutional ranking.

    The opportunity contains the final strategy-scoring result plus
    execution, return, risk, portfolio, and classification metadata.
    """

    symbol: str
    strategy: str
    direction: str
    market_regime: str

    strategy_score: float
    allowed: bool
    readiness: str
    recommendation: str

    expected_return_pct: float = 0.0
    expected_profit: float = 0.0
    maximum_loss: float = 0.0
    capital_required: float = 0.0

    probability_of_profit: float | None = None

    liquidity_score: float = 0.0
    execution_score: float = 0.0
    greeks_score: float = 0.0
    expected_move_score: float = 0.0
    data_confidence_score: float = 0.0
    risk_reward_score: float = 0.0
    portfolio_fit_score: float = 50.0

    strike: float | None = None
    long_strike: float | None = None
    short_strike: float | None = None

    expiry: str = ""
    dte: int = 0

    premium_type: str = ""
    risk_profile: str = "DEFINED_RISK"
    complexity: str = "STANDARD"

    sector: str = "UNKNOWN"
    industry: str = "UNKNOWN"
    correlation_group: str = ""

    option_symbol: str = ""
    contracts: int = 1

    rank_eligible: bool = True

    rejection_reasons: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    strategy_scoring_result: Any = None
    strategy_candidate: Any = None
    strike_candidate: Any = None
    expiration_candidate: Any = None
    greeks_profile: Any = None
    liquidity_profile: Any = None
    expected_move_profile: Any = None
    volatility_profile: Any = None

    metadata: dict = field(default_factory=dict)

    def __post_init__(self):
        self.symbol = str(self.symbol or "").upper()
        self.strategy = str(self.strategy or "").upper()
        self.direction = str(self.direction or "").upper()
        self.market_regime = str(
            self.market_regime or "UNKNOWN"
        ).upper()

        self.readiness = str(
            self.readiness or "RESEARCH_ONLY"
        ).upper()

        self.recommendation = str(
            self.recommendation or "RESEARCH_ONLY"
        ).upper()

        self.premium_type = str(
            self.premium_type or ""
        ).upper()

        self.risk_profile = str(
            self.risk_profile or "DEFINED_RISK"
        ).upper()

        self.complexity = str(
            self.complexity or "STANDARD"
        ).upper()

        self.sector = str(
            self.sector or "UNKNOWN"
        ).upper()

        self.industry = str(
            self.industry or "UNKNOWN"
        ).upper()

        self.correlation_group = str(
            self.correlation_group or ""
        ).upper()

        self.contracts = max(
            int(self.contracts or 1),
            1,
        )
