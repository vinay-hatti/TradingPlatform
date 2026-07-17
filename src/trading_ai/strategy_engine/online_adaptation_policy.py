from dataclasses import dataclass, field


@dataclass(frozen=True)
class OnlineAdaptationPolicy:
    """Policy governing controlled online strategy-weight adaptation."""

    minimum_observations_per_update: int = 10
    minimum_confidence_score: float = 55.0
    maximum_absolute_weight_change: float = 0.10
    maximum_relative_weight_change: float = 0.35
    minimum_strategy_weight: float = 0.02
    maximum_strategy_weight: float = 0.80
    learning_rate: float = 0.25
    stability_penalty_weight: float = 0.30
    confidence_weight: float = 0.35
    performance_weight: float = 0.35
    minimum_promotion_score: float = 60.0
    minimum_champion_improvement: float = 2.0
    require_all_strategies_allowed: bool = False
    allow_automatic_promotion: bool = False
    registry_schema_version: str = "1.0"
    metadata: dict[str, object] = field(default_factory=dict)

    def normalized_update_components(self) -> dict[str, float]:
        values = {
            "performance": max(float(self.performance_weight), 0.0),
            "confidence": max(float(self.confidence_weight), 0.0),
            "stability": max(float(self.stability_penalty_weight), 0.0),
        }
        total = sum(values.values())
        if total <= 0.0:
            return {"performance": 1.0, "confidence": 0.0, "stability": 0.0}
        return {name: value / total for name, value in values.items()}
