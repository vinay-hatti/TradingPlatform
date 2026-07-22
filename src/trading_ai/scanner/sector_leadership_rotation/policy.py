from dataclasses import dataclass


@dataclass(frozen=True)
class SectorLeadershipPolicy:
    benchmark_symbol: str = "SPY"

    minimum_sectors_ready: int = 9
    minimum_sectors_review: int = 6

    leader_count: int = 3
    laggard_count: int = 3

    return_5d_weight: float = 0.25
    relative_strength_21d_weight: float = 0.50
    trend_direction_weight: float = 0.15
    trend_strength_weight: float = 0.10

    risk_on_leadership_threshold: float = 0.10
    risk_off_leadership_threshold: float = -0.10
    broad_participation_threshold: float = 0.60
    narrow_participation_threshold: float = 0.40
