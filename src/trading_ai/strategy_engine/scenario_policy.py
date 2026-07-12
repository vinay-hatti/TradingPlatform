from dataclasses import dataclass, field

from trading_ai.strategy_engine.scenario_definition import (
    ScenarioDefinition,
)


@dataclass
class ScenarioPolicy:
    """
    Institutional strategy and portfolio stress-testing policy.
    """

    risk_free_rate: float = 0.04
    dividend_yield: float = 0.0

    annual_calendar_days: int = 365

    minimum_volatility: float = 0.01
    maximum_volatility: float = 3.00

    minimum_underlying_price: float = 0.01

    # Candidate-level limits
    maximum_stress_loss_pct_of_capital: float = 0.08
    maximum_stress_loss_pct_of_max_loss: float = 1.00

    # Portfolio-level limits
    maximum_portfolio_stress_loss_pct: float = 0.12
    warning_portfolio_stress_loss_pct: float = 0.08

    require_defined_risk: bool = True
    reject_unpriceable_scenarios: bool = True

    severe_loss_threshold_pct: float = 0.05
    critical_loss_threshold_pct: float = 0.10

    scenarios: list[ScenarioDefinition] = field(
        default_factory=list
    )

    def __post_init__(self):
        if not self.scenarios:
            self.scenarios = self.default_scenarios()

        self.validate()

    def validate(self) -> None:
        if self.annual_calendar_days <= 0:
            raise ValueError(
                "annual_calendar_days must be greater than zero"
            )

        if self.minimum_volatility <= 0:
            raise ValueError(
                "minimum_volatility must be greater than zero"
            )

        if (
            self.maximum_volatility
            <= self.minimum_volatility
        ):
            raise ValueError(
                "maximum_volatility must exceed minimum_volatility"
            )

        percentage_fields = {
            "maximum_stress_loss_pct_of_capital":
                self.maximum_stress_loss_pct_of_capital,
            "maximum_stress_loss_pct_of_max_loss":
                self.maximum_stress_loss_pct_of_max_loss,
            "maximum_portfolio_stress_loss_pct":
                self.maximum_portfolio_stress_loss_pct,
            "warning_portfolio_stress_loss_pct":
                self.warning_portfolio_stress_loss_pct,
            "severe_loss_threshold_pct":
                self.severe_loss_threshold_pct,
            "critical_loss_threshold_pct":
                self.critical_loss_threshold_pct,
        }

        for name, value in percentage_fields.items():
            if value < 0:
                raise ValueError(
                    f"{name} cannot be negative"
                )

    @staticmethod
    def default_scenarios() -> list[ScenarioDefinition]:
        return [
            ScenarioDefinition(
                name="BASE",
                description="No market shock",
                category="BASE",
                severity="NORMAL",
            ),
            ScenarioDefinition(
                name="PRICE_DOWN_5",
                description="Underlying falls 5%",
                underlying_shock_pct=-0.05,
                category="PRICE",
                severity="MODERATE",
            ),
            ScenarioDefinition(
                name="PRICE_DOWN_10",
                description="Underlying falls 10%",
                underlying_shock_pct=-0.10,
                category="PRICE",
                severity="SEVERE",
            ),
            ScenarioDefinition(
                name="PRICE_DOWN_20",
                description="Underlying falls 20%",
                underlying_shock_pct=-0.20,
                category="PRICE",
                severity="CRITICAL",
            ),
            ScenarioDefinition(
                name="PRICE_UP_5",
                description="Underlying rises 5%",
                underlying_shock_pct=0.05,
                category="PRICE",
                severity="MODERATE",
            ),
            ScenarioDefinition(
                name="PRICE_UP_10",
                description="Underlying rises 10%",
                underlying_shock_pct=0.10,
                category="PRICE",
                severity="SEVERE",
            ),
            ScenarioDefinition(
                name="PRICE_UP_20",
                description="Underlying rises 20%",
                underlying_shock_pct=0.20,
                category="PRICE",
                severity="CRITICAL",
            ),
            ScenarioDefinition(
                name="VOL_DOWN_25",
                description="Implied volatility falls 25%",
                volatility_shock_pct=-0.25,
                category="VOLATILITY",
                severity="MODERATE",
            ),
            ScenarioDefinition(
                name="VOL_UP_25",
                description="Implied volatility rises 25%",
                volatility_shock_pct=0.25,
                category="VOLATILITY",
                severity="MODERATE",
            ),
            ScenarioDefinition(
                name="VOL_UP_50",
                description="Implied volatility rises 50%",
                volatility_shock_pct=0.50,
                category="VOLATILITY",
                severity="SEVERE",
            ),
            ScenarioDefinition(
                name="TIME_FORWARD_7",
                description="Seven calendar days pass",
                days_forward=7,
                category="TIME",
                severity="MODERATE",
            ),
            ScenarioDefinition(
                name="TIME_FORWARD_14",
                description="Fourteen calendar days pass",
                days_forward=14,
                category="TIME",
                severity="SEVERE",
            ),
            ScenarioDefinition(
                name="CRASH_VOL_SPIKE",
                description=(
                    "Underlying falls 15%, IV rises 60%, "
                    "and three days pass"
                ),
                underlying_shock_pct=-0.15,
                volatility_shock_pct=0.60,
                days_forward=3,
                category="COMBINED",
                severity="CRITICAL",
            ),
            ScenarioDefinition(
                name="MELT_UP_VOL_CRUSH",
                description=(
                    "Underlying rises 12%, IV falls 35%, "
                    "and three days pass"
                ),
                underlying_shock_pct=0.12,
                volatility_shock_pct=-0.35,
                days_forward=3,
                category="COMBINED",
                severity="SEVERE",
            ),
            ScenarioDefinition(
                name="SIDEWAYS_THETA_DECAY",
                description=(
                    "Underlying unchanged, IV falls 15%, "
                    "and ten days pass"
                ),
                volatility_shock_pct=-0.15,
                days_forward=10,
                category="COMBINED",
                severity="MODERATE",
            ),
            ScenarioDefinition(
                name="RATE_UP_100BP",
                description="Risk-free rate rises by 1%",
                risk_free_rate_shock=0.01,
                category="RATE",
                severity="MODERATE",
            ),
        ]
