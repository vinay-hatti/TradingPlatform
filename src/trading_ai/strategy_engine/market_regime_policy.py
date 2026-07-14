from dataclasses import dataclass, field
from typing import Tuple


@dataclass(frozen=True)
class MarketRegimePolicy:
    """Institutional policy for deterministic market-regime detection."""

    short_window: int = 20
    medium_window: int = 50
    long_window: int = 100
    volatility_window: int = 20
    drawdown_window: int = 60
    minimum_observations: int = 120

    annualization_factor: float = 252.0
    trend_threshold: float = 0.015
    strong_trend_threshold: float = 0.050
    high_volatility_threshold: float = 0.30
    low_volatility_threshold: float = 0.12
    stress_volatility_threshold: float = 0.45
    stress_drawdown_threshold: float = -0.12
    recovery_drawdown_threshold: float = -0.04
    momentum_threshold: float = 0.02

    minimum_confidence_score: float = 45.0
    minimum_regime_score: float = 40.0
    reject_invalid_profile: bool = False
    reject_critical_regime: bool = False

    supported_regimes: Tuple[str, ...] = field(
        default=(
            "STRONG_BULL_TREND",
            "BULL_TREND",
            "STRONG_BEAR_TREND",
            "BEAR_TREND",
            "HIGH_VOLATILITY",
            "LOW_VOLATILITY_RANGE",
            "RANGE_BOUND",
            "STRESS",
            "RECOVERY",
            "TRANSITION",
            "UNKNOWN",
        )
    )

    def __post_init__(self):
        integer_fields = (
            "short_window",
            "medium_window",
            "long_window",
            "volatility_window",
            "drawdown_window",
            "minimum_observations",
        )
        for name in integer_fields:
            if int(getattr(self, name)) <= 0:
                raise ValueError(f"{name} must be positive")

        if not (
            self.short_window
            <= self.medium_window
            <= self.long_window
        ):
            raise ValueError(
                "short_window <= medium_window <= long_window is required"
            )

        for name in (
            "minimum_confidence_score",
            "minimum_regime_score",
        ):
            value = float(getattr(self, name))
            if not 0.0 <= value <= 100.0:
                raise ValueError(f"{name} must be between 0 and 100")
