from dataclasses import dataclass


@dataclass(frozen=True)
class SegmentedProbabilityCalibrationPolicy:
    segment_dimensions: tuple[str, ...] = (
        "strategy", "market_regime", "direction"
    )
    minimum_segment_observations: int = 125
    minimum_segment_positive_observations: int = 25
    minimum_segment_negative_observations: int = 25
    maximum_segment_depth: int = 2
    train_global_model: bool = True
    require_allowed_segment_model: bool = True
    fallback_order: tuple[str, ...] = (
        "STRATEGY_MARKET_REGIME", "STRATEGY_DIRECTION", "STRATEGY",
        "MARKET_REGIME", "DIRECTION", "GLOBAL"
    )

    def validate(self) -> None:
        allowed = {"symbol", "strategy", "market_regime", "direction"}
        if not self.segment_dimensions:
            raise ValueError("segment_dimensions cannot be empty")
        if any(item not in allowed for item in self.segment_dimensions):
            raise ValueError("unsupported segment dimension")
        if self.minimum_segment_observations < 20:
            raise ValueError("minimum_segment_observations must be at least 20")
        if not 1 <= self.maximum_segment_depth <= len(self.segment_dimensions):
            raise ValueError("maximum_segment_depth is invalid")
