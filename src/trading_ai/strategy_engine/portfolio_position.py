from dataclasses import dataclass, field
from typing import Any


@dataclass
class PortfolioPosition:
    symbol: str
    strategy: str
    direction: str

    contracts: int

    capital_required: float
    maximum_loss: float
    expected_profit: float
    expected_return_pct: float

    allocation_pct: float
    risk_pct: float

    delta: float
    gamma: float
    theta: float
    vega: float
    rho: float

    sector: str
    industry: str
    correlation_group: str

    ranking_score: float
    strategy_score: float
    portfolio_fit_score: float

    readiness: str
    action: str

    expiry: str = ""
    dte: int = 0

    strike: float | None = None
    long_strike: float | None = None
    short_strike: float | None = None

    option_symbol: str = ""

    premium_type: str = ""
    risk_profile: str = "DEFINED_RISK"
    complexity: str = "STANDARD"

    source_opportunity: Any = None
    source_ranked_opportunity: Any = None

    warnings: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)

    def __post_init__(self):
        self.symbol = str(self.symbol or "").upper()
        self.strategy = str(self.strategy or "").upper()
        self.direction = str(self.direction or "").upper()

        self.sector = str(
            self.sector or "UNKNOWN"
        ).upper()

        self.industry = str(
            self.industry or "UNKNOWN"
        ).upper()

        self.correlation_group = str(
            self.correlation_group or ""
        ).upper()

        self.readiness = str(
            self.readiness or "RESEARCH_ONLY"
        ).upper()

        self.action = str(
            self.action or "WATCHLIST"
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

        self.contracts = max(
            int(self.contracts or 1),
            1,
        )

        self.capital_required = max(
            float(self.capital_required or 0.0),
            0.0,
        )

        self.maximum_loss = max(
            float(self.maximum_loss or 0.0),
            0.0,
        )

    @property
    def is_bullish(self) -> bool:
        return self.direction == "CALL"

    @property
    def is_bearish(self) -> bool:
        return self.direction == "PUT"

    @property
    def is_neutral(self) -> bool:
        return self.direction == "NEUTRAL"
