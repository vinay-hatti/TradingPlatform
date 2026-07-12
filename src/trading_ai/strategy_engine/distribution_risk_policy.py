from dataclasses import dataclass


@dataclass(frozen=True)
class DistributionRiskPolicy:
    """
    Institutional distribution and tail-risk policy.
    """

    confidence_level: float = 0.95
    secondary_confidence_level: float = 0.99

    annualization_factor: int = 252
    risk_free_rate: float = 0.04

    minimum_observations: int = 30
    preferred_observations: int = 100

    downside_target_return: float = 0.0
    omega_threshold_return: float = 0.0

    large_loss_threshold_pct: float = 0.05
    severe_loss_threshold_pct: float = 0.10
    critical_loss_threshold_pct: float = 0.20

    maximum_var_pct_of_capital: float = 0.05
    maximum_expected_shortfall_pct_of_capital: float = 0.08
    maximum_drawdown_at_risk_pct: float = 0.12

    maximum_negative_skew: float = -1.00
    maximum_excess_kurtosis: float = 5.00

    minimum_sortino_ratio: float = 0.50
    minimum_omega_ratio: float = 1.00

    reject_insufficient_observations: bool = False
    reject_tail_limit_breaches: bool = True

    finite_difference_epsilon: float = 0.01

    def validate(self) -> None:
        for name, value in {
            "confidence_level": self.confidence_level,
            "secondary_confidence_level":
                self.secondary_confidence_level,
        }.items():
            if not 0.50 < value < 1.0:
                raise ValueError(
                    f"{name} must be between 0.50 and 1.0"
                )

        if (
            self.secondary_confidence_level
            <= self.confidence_level
        ):
            raise ValueError(
                "secondary_confidence_level must exceed "
                "confidence_level"
            )

        if self.annualization_factor <= 0:
            raise ValueError(
                "annualization_factor must be positive"
            )

        if self.minimum_observations < 2:
            raise ValueError(
                "minimum_observations must be at least 2"
            )

        if self.preferred_observations < self.minimum_observations:
            raise ValueError(
                "preferred_observations must be at least "
                "minimum_observations"
            )

        if self.finite_difference_epsilon <= 0:
            raise ValueError(
                "finite_difference_epsilon must be positive"
            )
