from dataclasses import dataclass


@dataclass(frozen=True)
class ScenarioDefinition:
    """
    Defines one deterministic market stress scenario.

    Price and volatility shocks are represented as decimal percentages:

        -0.10 = underlying falls 10%
         0.20 = volatility rises 20%

    Volatility shock is applied relatively by default:

        stressed_iv = base_iv * (1 + volatility_shock_pct)
    """

    name: str
    description: str = ""

    underlying_shock_pct: float = 0.0
    volatility_shock_pct: float = 0.0

    days_forward: int = 0

    risk_free_rate_shock: float = 0.0
    dividend_yield_shock: float = 0.0

    probability_weight: float | None = None

    category: str = "CUSTOM"
    severity: str = "NORMAL"

    enabled: bool = True

    def __post_init__(self):
        if not str(self.name or "").strip():
            raise ValueError(
                "ScenarioDefinition requires a name"
            )

        if self.days_forward < 0:
            raise ValueError(
                "days_forward cannot be negative"
            )

        if (
            self.probability_weight is not None
            and (
                self.probability_weight < 0
                or self.probability_weight > 1
            )
        ):
            raise ValueError(
                "probability_weight must be between 0 and 1"
            )
