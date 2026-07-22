from dataclasses import dataclass

@dataclass(frozen=True)
class CrossAssetFeaturePolicy:
    minimum_observations_ready: int = 60
    minimum_observations_review: int = 22
    minimum_latest_close: float = 0.01
    minimum_average_volume_20d_ready: float = 100_000.0
    minimum_average_volume_20d_review: float = 10_000.0
    annualization_factor: int = 252
    maximum_atr_pct_ready: float = 0.15
    maximum_atr_pct_review: float = 0.30
    require_benchmark_for_relative_strength: bool = False
