from dataclasses import dataclass


@dataclass(frozen=True)
class MarketRegimeForecastPolicy:
    """Policy for transition-probability and persistence forecasting."""

    minimum_history_observations: int = 40
    minimum_transition_count: int = 8
    laplace_smoothing: float = 1.0
    forecast_horizon: int = 5
    recent_transition_lookback: int = 120
    persistence_warning_threshold: float = 0.45
    transition_warning_threshold: float = 0.55
    minimum_forecast_confidence: float = 40.0
    minimum_forecast_score: float = 40.0
    reject_invalid_profile: bool = False
    reject_critical_forecast: bool = False

    def __post_init__(self):
        for name in (
            "minimum_history_observations",
            "minimum_transition_count",
            "forecast_horizon",
            "recent_transition_lookback",
        ):
            if int(getattr(self, name)) <= 0:
                raise ValueError(f"{name} must be positive")
        if float(self.laplace_smoothing) < 0.0:
            raise ValueError("laplace_smoothing must be non-negative")
        for name in (
            "persistence_warning_threshold",
            "transition_warning_threshold",
        ):
            value = float(getattr(self, name))
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"{name} must be between 0 and 1")
        for name in (
            "minimum_forecast_confidence",
            "minimum_forecast_score",
        ):
            value = float(getattr(self, name))
            if not 0.0 <= value <= 100.0:
                raise ValueError(f"{name} must be between 0 and 100")
