from dataclasses import dataclass


@dataclass(frozen=True)
class ProbabilityPolicy:
    simulation_count: int = 50000
    random_seed: int = 42

    risk_free_rate: float = 0.04
    dividend_yield: float = 0.0

    annual_calendar_days: int = 365

    breakeven_tolerance_dollars: float = 0.01
    max_profit_tolerance_pct: float = 0.02
    max_loss_tolerance_pct: float = 0.02

    profit_target_pct_of_max_profit: float = 0.50
    stop_loss_pct_of_max_loss: float = 0.50

    minimum_volatility: float = 0.01
    maximum_volatility: float = 3.00

    minimum_simulations: int = 1000
    maximum_simulations: int = 1000000

    use_risk_neutral_drift: bool = True

    def validate(self) -> None:
        if self.simulation_count < self.minimum_simulations:
            raise ValueError(
                "simulation_count is below the minimum"
            )

        if self.simulation_count > self.maximum_simulations:
            raise ValueError(
                "simulation_count exceeds the maximum"
            )

        if self.annual_calendar_days <= 0:
            raise ValueError(
                "annual_calendar_days must be greater than zero"
            )

        if not 0 < self.profit_target_pct_of_max_profit <= 1:
            raise ValueError(
                "profit_target_pct_of_max_profit must be between 0 and 1"
            )

        if not 0 < self.stop_loss_pct_of_max_loss <= 1:
            raise ValueError(
                "stop_loss_pct_of_max_loss must be between 0 and 1"
            )
