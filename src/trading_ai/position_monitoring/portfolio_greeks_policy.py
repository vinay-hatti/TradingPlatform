from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PortfolioGreeksMonitoringPolicy:
    """Govern real-time portfolio Greeks and scenario-risk monitoring."""

    maximum_absolute_delta: float = 25000.0
    maximum_absolute_gamma: float = 10000.0
    maximum_absolute_vega: float = 500000.0
    maximum_absolute_theta: float = 250000.0
    maximum_absolute_rho: float = 250000.0
    maximum_underlying_delta: float = 10000.0
    maximum_underlying_gamma: float = 5000.0
    maximum_underlying_vega: float = 200000.0
    maximum_scenario_loss: float = 100000.0
    maximum_scenario_loss_pct_of_equity: float = 0.25
    maximum_underlying_scenario_loss: float = 50000.0
    maximum_surface_points: int = 10000
    require_greeks_for_option_positions: bool = True
    require_underlying_prices: bool = True
    reject_stale_greeks: bool = True
    maximum_greeks_age_seconds: int = 60
    scenario_underlying_shocks_pct: tuple[float, ...] = (
        -0.20,
        -0.10,
        -0.05,
        0.05,
        0.10,
        0.20,
    )
    scenario_volatility_shocks: tuple[float, ...] = (-0.20, -0.10, 0.10, 0.20)
    scenario_time_decay_days: tuple[int, ...] = (1, 5, 10, 20)
    minimum_monitoring_score: float = 85.0
    fail_closed: bool = True

    def validate(self) -> None:
        for name in (
            "maximum_absolute_delta",
            "maximum_absolute_gamma",
            "maximum_absolute_vega",
            "maximum_absolute_theta",
            "maximum_absolute_rho",
            "maximum_underlying_delta",
            "maximum_underlying_gamma",
            "maximum_underlying_vega",
            "maximum_scenario_loss",
            "maximum_underlying_scenario_loss",
        ):
            if getattr(self, name) <= 0:
                raise ValueError(f"{name} must be positive")
        if not 0 < self.maximum_scenario_loss_pct_of_equity <= 1:
            raise ValueError(
                "maximum_scenario_loss_pct_of_equity must be in (0, 1]"
            )
        if self.maximum_surface_points <= 0:
            raise ValueError("maximum_surface_points must be positive")
        if self.maximum_greeks_age_seconds <= 0:
            raise ValueError("maximum_greeks_age_seconds must be positive")
        if not self.scenario_underlying_shocks_pct:
            raise ValueError("scenario_underlying_shocks_pct cannot be empty")
        if not 0 <= self.minimum_monitoring_score <= 100:
            raise ValueError(
                "minimum_monitoring_score must be between 0 and 100"
            )
