from dataclasses import dataclass


@dataclass(frozen=True)
class CorrelationDispersionPolicy:
    minimum_symbols_ready: int = 8
    minimum_symbols_review: int = 5

    minimum_pair_observations_21d: int = 15
    minimum_pair_observations_63d: int = 40

    high_correlation_threshold: float = 0.65
    low_correlation_threshold: float = 0.25
    breakdown_change_threshold: float = 0.35

    high_dispersion_threshold: float = 0.025
    low_dispersion_threshold: float = 0.010

    strongest_pair_count: int = 5
    maximum_breakdown_ratio_ready: float = 0.30
    maximum_breakdown_ratio_review: float = 0.60
