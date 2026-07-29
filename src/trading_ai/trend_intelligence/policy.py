from dataclasses import dataclass

@dataclass(frozen=True)
class TrendIntelligencePolicy:
    short_fast: int = 5
    short_slow: int = 21
    intermediate_fast: int = 20
    intermediate_slow: int = 65
    long_fast: int = 50
    long_slow: int = 200
    slope_lookback_short: int = 5
    slope_lookback_intermediate: int = 20
    slope_lookback_long: int = 60
    minimum_history_days: int = 220
    relative_strength_lookback: int = 63
    maximum_scanner_adjustment: float = 12.0
    scanner_weight: float = 0.12
