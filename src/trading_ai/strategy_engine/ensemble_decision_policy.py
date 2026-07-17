from dataclasses import dataclass


@dataclass(frozen=True)
class EnsembleDecisionPolicy:
    adaptive_weight: float = 0.40
    learned_weight: float = 0.25
    probability_weight: float = 0.15
    regime_weight: float = 0.10
    execution_weight: float = 0.10
    minimum_component_count: int = 3
    minimum_ensemble_score: float = 60.0
    minimum_meta_confidence: float = 55.0
    minimum_consensus_ratio: float = 0.60
    maximum_score_dispersion: float = 25.0
    reject_on_direction_conflict: bool = True
    fallback_to_adaptive_selection: bool = True

    def normalized_weights(self) -> dict[str, float]:
        values = {
            "adaptive": max(0.0, self.adaptive_weight),
            "learned": max(0.0, self.learned_weight),
            "probability": max(0.0, self.probability_weight),
            "regime": max(0.0, self.regime_weight),
            "execution": max(0.0, self.execution_weight),
        }
        total = sum(values.values())
        if total <= 0.0:
            return {name: 0.2 for name in values}
        return {name: value / total for name, value in values.items()}
