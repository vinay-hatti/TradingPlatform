from dataclasses import dataclass, field
from typing import Any


@dataclass
class DecisionCandidateBundle:
    """
    Stores all intermediate Phase 1-10 results for one candidate.
    """

    symbol: str
    direction: str
    market_regime: str
    technical_score: float

    underlying_price: float

    strategy_candidate: Any = None
    expiration_candidate: Any = None
    strike_candidate: Any = None

    volatility_profile: Any = None
    expected_move_profile: Any = None
    greeks_profile: Any = None
    liquidity_profile: Any = None
    payoff_profile: Any = None

    strategy_scoring_context: Any = None
    strategy_scoring_result: Any = None

    institutional_opportunity: Any = None
    ranked_opportunity: Any = None
    portfolio_position: Any = None

    candidate_id: str = ""

    allowed: bool = True
    rejection_reasons: list[str] = field(
        default_factory=list
    )

    warnings: list[str] = field(
        default_factory=list
    )

    metadata: dict = field(
        default_factory=dict
    )

    def __post_init__(self):
        self.symbol = str(
            self.symbol or ""
        ).upper()

        self.direction = str(
            self.direction or "NEUTRAL"
        ).upper()

        self.market_regime = str(
            self.market_regime or "UNKNOWN"
        ).upper()

        self.technical_score = float(
            self.technical_score or 0.0
        )

        self.underlying_price = float(
            self.underlying_price or 0.0
        )

    @property
    def strategy(self) -> str:
        if self.strategy_candidate is None:
            return ""

        return str(
            getattr(
                self.strategy_candidate,
                "strategy",
                "",
            )
            or ""
        ).upper()

    @property
    def expiry(self) -> str:
        if self.expiration_candidate is not None:
            value = getattr(
                self.expiration_candidate,
                "expiry",
                "",
            )

            if value:
                return str(value)

        if self.strike_candidate is not None:
            return str(
                getattr(
                    self.strike_candidate,
                    "expiry",
                    "",
                )
                or ""
            )

        return ""

    @property
    def dte(self) -> int:
        if self.expiration_candidate is not None:
            value = getattr(
                self.expiration_candidate,
                "dte",
                0,
            )

            if value:
                return int(value)

        if self.strike_candidate is not None:
            return int(
                getattr(
                    self.strike_candidate,
                    "dte",
                    0,
                )
                or 0
            )

        return 0
