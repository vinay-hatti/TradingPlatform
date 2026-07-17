from dataclasses import dataclass, field


@dataclass(frozen=True)
class StrategyLearningPolicy:
    """Governance policy for historical strategy learning and dynamic weighting."""

    minimum_observations: int = 30
    minimum_segment_observations: int = 15
    recency_half_life_days: float = 90.0
    maximum_history_days: int = 1095
    winsorize_return_pct: float = 0.50
    minimum_effective_sample_size: float = 10.0
    minimum_weight: float = 0.05
    maximum_weight: float = 0.75
    base_prior_weight: float = 0.35
    performance_weight: float = 0.40
    stability_weight: float = 0.15
    recency_weight: float = 0.10
    reject_invalid_records: bool = True
    preserve_unknown_context: bool = True
    context_keys: tuple[str, ...] = (
        "market_regime",
        "volatility_regime",
        "direction",
    )
    metadata: dict[str, object] = field(default_factory=dict)

    def normalized_components(self) -> dict[str, float]:
        values = {
            "prior": max(float(self.base_prior_weight), 0.0),
            "performance": max(float(self.performance_weight), 0.0),
            "stability": max(float(self.stability_weight), 0.0),
            "recency": max(float(self.recency_weight), 0.0),
        }
        total = sum(values.values())
        if total <= 0.0:
            return {"prior": 1.0, "performance": 0.0, "stability": 0.0, "recency": 0.0}
        return {name: value / total for name, value in values.items()}
