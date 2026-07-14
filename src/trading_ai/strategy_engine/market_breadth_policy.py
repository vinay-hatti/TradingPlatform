from dataclasses import dataclass


@dataclass(frozen=True)
class MarketBreadthPolicy:
    minimum_symbols: int = 3
    bullish_regimes: tuple[str, ...] = (
        "STRONG_BULL_TREND", "BULL_TREND", "RECOVERY"
    )
    bearish_regimes: tuple[str, ...] = (
        "STRONG_BEAR_TREND", "BEAR_TREND", "STRESS"
    )
    stressed_regimes: tuple[str, ...] = ("STRESS",)
    minimum_bullish_breadth: float = 0.55
    severe_bearish_breadth: float = 0.60
    critical_stress_breadth: float = 0.35
    maximum_dispersion: float = 0.45
    maximum_concentration: float = 0.55
    minimum_breadth_score: float = 50.0
    reject_invalid_profile: bool = False
    reject_critical_market_state: bool = False
