from dataclasses import dataclass


@dataclass(frozen=True)
class PortfolioRiskLimits:
    initial_capital: float = 100000.0

    # -----------------------------------------
    # Capital and risk limits
    # -----------------------------------------

    maximum_portfolio_exposure_pct: float = 0.50
    maximum_total_risk_pct: float = 0.20

    maximum_position_pct: float = 0.10
    maximum_risk_per_trade_pct: float = 0.03

    minimum_position_dollars: float = 100.0
    maximum_contracts_per_position: int = 20

    reserve_cash_pct: float = 0.20

    # -----------------------------------------
    # Concentration limits
    # -----------------------------------------

    maximum_positions: int = 10

    maximum_positions_per_symbol: int = 1
    maximum_positions_per_sector: int = 3
    maximum_positions_per_strategy: int = 3
    maximum_positions_per_direction: int = 5
    maximum_positions_per_correlation_group: int = 2

    maximum_symbol_exposure_pct: float = 0.12
    maximum_sector_exposure_pct: float = 0.30
    maximum_strategy_exposure_pct: float = 0.35
    maximum_direction_exposure_pct: float = 0.60
    maximum_correlation_group_exposure_pct: float = 0.25

    # -----------------------------------------
    # Greeks limits
    # Values are portfolio-level totals
    # -----------------------------------------

    maximum_absolute_delta: float = 500.0
    maximum_absolute_gamma: float = 25.0
    maximum_absolute_theta: float = 1000.0
    maximum_absolute_vega: float = 2500.0
    maximum_absolute_rho: float = 2500.0

    # Optional directional delta bands
    minimum_net_delta: float = -500.0
    maximum_net_delta: float = 500.0

    # -----------------------------------------
    # Candidate quality requirements
    # -----------------------------------------

    minimum_ranking_score: float = 60.0
    minimum_strategy_score: float = 65.0
    minimum_portfolio_fit_score: float = 40.0

    allow_research_positions: bool = False
    allow_undefined_risk: bool = False
    allow_zero_maximum_loss: bool = False

    # -----------------------------------------
    # Allocation behavior
    # -----------------------------------------

    use_risk_based_sizing: bool = True
    use_score_scaling: bool = True

    minimum_score_multiplier: float = 0.50
    maximum_score_multiplier: float = 1.25

    def validate(self) -> None:
        if self.initial_capital <= 0:
            raise ValueError(
                "initial_capital must be greater than zero"
            )

        percentage_fields = {
            "maximum_portfolio_exposure_pct":
                self.maximum_portfolio_exposure_pct,
            "maximum_total_risk_pct":
                self.maximum_total_risk_pct,
            "maximum_position_pct":
                self.maximum_position_pct,
            "maximum_risk_per_trade_pct":
                self.maximum_risk_per_trade_pct,
            "reserve_cash_pct":
                self.reserve_cash_pct,
            "maximum_symbol_exposure_pct":
                self.maximum_symbol_exposure_pct,
            "maximum_sector_exposure_pct":
                self.maximum_sector_exposure_pct,
            "maximum_strategy_exposure_pct":
                self.maximum_strategy_exposure_pct,
            "maximum_direction_exposure_pct":
                self.maximum_direction_exposure_pct,
            "maximum_correlation_group_exposure_pct":
                self.maximum_correlation_group_exposure_pct,
        }

        for name, value in percentage_fields.items():
            if value < 0 or value > 1:
                raise ValueError(
                    f"{name} must be between 0 and 1"
                )

        if (
            self.maximum_portfolio_exposure_pct
            + self.reserve_cash_pct
            > 1.0
        ):
            raise ValueError(
                "portfolio exposure plus reserve cash cannot exceed 100%"
            )

        if self.maximum_positions <= 0:
            raise ValueError(
                "maximum_positions must be greater than zero"
            )

    @property
    def maximum_portfolio_exposure_dollars(self) -> float:
        return (
            self.initial_capital
            * self.maximum_portfolio_exposure_pct
        )

    @property
    def maximum_total_risk_dollars(self) -> float:
        return (
            self.initial_capital
            * self.maximum_total_risk_pct
        )

    @property
    def maximum_position_dollars(self) -> float:
        return (
            self.initial_capital
            * self.maximum_position_pct
        )

    @property
    def maximum_risk_per_trade_dollars(self) -> float:
        return (
            self.initial_capital
            * self.maximum_risk_per_trade_pct
        )

    @property
    def reserve_cash_dollars(self) -> float:
        return (
            self.initial_capital
            * self.reserve_cash_pct
        )
